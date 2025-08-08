import { generateKeyPairSync } from "crypto";
import { app, BrowserWindow, ipcMain, dialog, safeStorage } from "electron";
import { stat } from "fs/promises";
import * as path from "path";
import * as fs from "fs";
import * as net from "net";

interface ProcessingParams {
  action: number;
  resolution?: string;
  aspect_ratio?: string;
  startseconds?: number;
  endseconds?: number;
  extension?: string;
  outputFileName?: string;
}

interface ProcessingRequest {
  filePath: string;
  requestParams: ProcessingParams;
}

interface ServerConfig {
  server_address: string;
  server_port: number;
  stream_rate: number;
}

interface KeyPaths {
  securePrivatePath: string;
  publicPath: string;
}

function generateCryptoKeys(): void {
  const { publicKey, privateKey } = generateKeyPairSync("rsa", {
    modulusLength: 2048,
    publicKeyEncoding: {
      type: "spki",
      format: "pem",
    },
    privateKeyEncoding: {
      type: "pkcs8",
      format: "pem",
    },
  });

  const encryptedKey = safeStorage.encryptString(privateKey);

  const saveDir = app.getPath("userData");
  const SecurePrivateKeyPath = path.join(saveDir, "key.secure");
  const PublicKeyPath = path.join(saveDir, "publicKey.pem");

  fs.writeFileSync(SecurePrivateKeyPath, encryptedKey);
  fs.writeFileSync(PublicKeyPath, publicKey);
}

function createWindow() {
  const win = new BrowserWindow({
    width: 800,
    height: 600,
    webPreferences: {
      preload: path.join(app.getAppPath(), "preload.js"),
    },
  });

  win.loadFile(path.join(__dirname, "index.html"));
  win.webContents.openDevTools(); // 開発時のみ
}

ipcMain.handle("open-video-dialog", async () => {
  const result = await dialog.showOpenDialog({
    properties: ["openFile"],
    filters: [
      {
        name: "Video Files",
        extensions: ["mp4"],
      },
    ],
  });

  if (!result.canceled && result.filePaths.length > 0) {
    return result.filePaths[0];
  }
  return null;
});

ipcMain.handle("get-file-stats", async (event, filePath: string) => {
  try {
    const stats = await stat(filePath);
    return {
      size: stats.size,
      isFile: stats.isFile(),
    };
  } catch (error) {
    return error;
  }
});

ipcMain.handle(
  "process-video-request",
  async (event, request: ProcessingRequest) => {
    try {
      const result = await processVideoRequest(request);

      return result;
    } catch (error) {
      throw error;
    }
  },
);

ipcMain.handle(
  "download-file",
  async (
    event,
    fileData: { filename: string; fileData: any; fileExtension: string },
  ) => {
    try {
      const result = await dialog.showSaveDialog({
        defaultPath: fileData.filename,
        filters: [
          { name: "Video Files", extensions: [fileData.fileExtension] },
          { name: "All Files", extensions: ["*"] },
        ],
      });

      if (!result.canceled && result.filePath) {
        let bufferToWrite;

        if (Buffer.isBuffer(fileData.fileData)) {
          bufferToWrite = fileData.fileData;
        } else {
          bufferToWrite = Buffer.from(fileData.fileData);
        }

        fs.writeFileSync(result.filePath, bufferToWrite);
        return { success: true, path: result.filePath };
      }

      return { success: false };
    } catch (error) {
      throw error;
    }
  },
);

function loadClientConfig(): ServerConfig {
  try {
    const configPath = path.join(__dirname, "..", "..", "config.json");

    const configData = fs.readFileSync(configPath, "utf-8");
    const config = JSON.parse(configData);

    return {
      server_address: config.server_address,
      server_port: config.server_port,
      stream_rate: config.stream_rate,
    };
  } catch (error) {
    throw error;
  }
}

function connectToServer(config: ServerConfig): Promise<net.Socket> {
  return new Promise((resolve, reject) => {
    const socket = new net.Socket();

    socket.connect(config.server_port, config.server_address, () => {
      resolve(socket);
    });

    socket.on("error", (error) => {
      reject(error);
    });

    socket.setTimeout(30000);
    socket.on("timeout", () => {
      socket.destroy();
      reject(new Error("Connection timeout"));
    });
  });
}

function createRequestHeader(
  jsonSize: number,
  mediatypeSize: number,
  payloadSize: number,
): Buffer {
  const header = Buffer.alloc(8);
  header.writeUIntBE(jsonSize, 0, 2);
  header.writeUIntBE(mediatypeSize, 2, 1);
  header.writeUIntBE(payloadSize, 3, 5);
  return header;
}

function getKeyPaths(): KeyPaths {
  const saveDir = app.getPath("userData");
  return {
    securePrivatePath: path.join(saveDir, "key.secure"),
    publicPath: path.join(saveDir, "publicKey.pem"),
  };
}

function receivePublicKeyInfo(socket: net.Socket): Promise<Buffer> {
  return new Promise((resolve, reject) => {
    const chunks: Buffer[] = [];
    let size: number | null = null;
    const headerLen = 4;

    // データ受信時のコールバック関数
    const onData = (chunk: Buffer) => {
      chunks.push(chunk);
      const buffer = Buffer.concat(chunks);

      // まだサイズ未取得で、ヘッダ分が揃ったら読む
      if (size === null && buffer.length >= headerLen) {
        // 4B長さヘッダの場合
        size = buffer.readUInt32BE(0);
      }

      // 本体が揃ったら一度だけ処理してリスナー解除
      if (size !== null && buffer.length >= headerLen + size) {
        const client_public_key = buffer.subarray(headerLen, headerLen + size);
        socket.off("data", onData);
        socket.off("error", onError);
        resolve(client_public_key);
      }
    };

    const onError = (err: Error) => {
      socket.off("data", onData);
      socket.off("error", onError);
      reject(err);
    };

    socket.on("data", onData);
    socket.on("error", onError);

    // timeoutがないと永遠にサーバーからのレスポンスを待ち続けるため、追加
    setTimeout(() => {
      socket.off("data", onData);
      socket.off("error", onError);
      reject(new Error("Read timeout"));
    }, 10000);

  });
}

async function exchangePublicKeys(
  socket: net.Socket,
  publicKeyPath: string,
): Promise<string> {
  try {
    const publicKey = fs.readFileSync(publicKeyPath, "utf-8");
    const keySize = Buffer.byteLength(publicKey, "utf8");
    const sizeBuffer = Buffer.alloc(4);
    sizeBuffer.writeUInt32BE(keySize, 0);

    socket.write(sizeBuffer);
    socket.write(publicKey, "utf8");
    console.log("クライアントの公開鍵を送信");

    console.log("サーバーの公開鍵を受信開始");
    const serverKeyBuffer = await receivePublicKeyInfo(socket);
    const serverPublicKey = serverKeyBuffer.toString("utf8");
    console.log("サーバーの公開鍵を受信完了");

    console.log("公開鍵の交換に成功");

    return serverPublicKey;
  } catch (error) {
    console.error("公開鍵の交換に失敗:", error);
    throw new Error(`公開鍵の交換に失敗：${error}`);
  }
}

function sendFileData(
  socket: net.Socket,
  filePath: string,
  requestParams: ProcessingParams,
  config: ServerConfig,
): Promise<void> {
  return new Promise((resolve, reject) => {
    try {
      const mediatype = path.extname(filePath).substring(1);
      const stats = fs.statSync(filePath);
      const fileSize = stats.size;

      const reqParamsJson = JSON.stringify(requestParams);
      const reqParamsSize = Buffer.byteLength(reqParamsJson, "utf8");
      const mediatypeSize = Buffer.byteLength(mediatype, "utf8");

      const header = createRequestHeader(
        reqParamsSize,
        mediatypeSize,
        fileSize,
      );
      socket.write(header);

      socket.write(reqParamsJson, "utf8");

      socket.write(mediatype, "utf8");

      const fileStream = fs.createReadStream(filePath, {
        highWaterMark: config.stream_rate,
      });

      fileStream.on("data", (chunk) => {
        socket.write(chunk);
      });

      fileStream.on("end", () => {
        resolve();
      });

      fileStream.on("error", (error) => {
        reject(error);
      });
    } catch (error) {
      reject(error);
    }
  });
}

function receiveResponse(socket: net.Socket): Promise<any> {
  return new Promise((resolve, reject) => {
    const chunks: Buffer[] = [];

    socket.on("data", (chunk: Buffer) => {
      chunks.push(chunk);
    });

    socket.on("end", () => {
      try {
        const buffer = Buffer.concat(chunks);

        const responseCode = buffer.readUIntBE(0, 1);
        const dataSize = buffer.readUIntBE(1, 4);

        if (responseCode === 0x00) {
          const errorText = buffer.subarray(5, 5 + dataSize).toString("utf-8");
          resolve({ status: "error", error: errorText });
        } else {
          const jsonData = buffer.subarray(5, 5 + dataSize);
          const successJson = JSON.parse(jsonData.toString("utf-8"));
          const fileData = buffer.subarray(5 + dataSize);

          resolve({
            status: "success",
            filename: `output.${successJson.file_extension}`,
            fileData: Array.from(fileData.subarray(0, successJson.file_size)),
            fileExtension: successJson.file_extension,
          });
        }
      } catch (error) {
        reject(error);
      }
    });

    socket.on("error", reject);
  });
}

async function processVideoRequest(request: ProcessingRequest): Promise<any> {
  const config = loadClientConfig();

  let socket: net.Socket | null = null;

  try {
    socket = await connectToServer(config);

    const { publicPath } = getKeyPaths();

    const serverKey = await exchangePublicKeys(socket, publicPath);
    console.log("サーバーの公開鍵を取得：", serverKey);

    await sendFileData(socket, request.filePath, request.requestParams, config);

    const response = await receiveResponse(socket);

    if (response.status === "error") {
      throw new Error(response.error);
    }

    const userFileName = request.requestParams.outputFileName || "output";
    const finalFileName = `${userFileName}.${response.fileExtension}`;

    return {
      status: "success",
      message: "Video processing completed successfully!",
      filename: finalFileName,
      fileExtension: response.fileExtension,
      fileData: Array.from(response.fileData),
    };
  } catch (error) {
    throw error;
  } finally {
    if (socket) {
      socket.destroy();
    }
  }
}

app.whenReady().then(() => {
  generateCryptoKeys();
  createWindow();
});

app.on("window-all-closed", () => {
  if (process.platform !== "darwin") app.quit();
});

app.on("activate", () => {
  if (BrowserWindow.getAllWindows().length === 0) {
    createWindow();
  }
});
