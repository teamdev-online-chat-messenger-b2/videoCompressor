import { app, BrowserWindow, ipcMain, dialog } from "electron";
import { stat } from "fs/promises";
import * as path from "path";
import * as fs from "fs";
import * as net from "net";

interface ProcessingRequest {
  filePath: string;
  requestParams: {
    action: number;
    resolution?: string;
    aspect_ratio?: string;
    startseconds?: number;
    endseconds?: number;
    extension?: string;
  };
}

interface ServerConfig {
  server_address: string;
  server_port: number;
  stream_rate: number;
}

function createWindow() {
  const win = new BrowserWindow({
    width: 800,
    height: 600,
    webPreferences: {
      preload: path.join(app.getAppPath(), "preload.js"),
      nodeIntegration: true,
      contextIsolation: true,
    },
  });

  win.loadFile(path.join(__dirname, "index.html"));
  win.webContents.openDevTools(); // 開発時のみ
}

ipcMain.handle("open-video-dialog", async () => {
  // eslint-disable-next-line @typescript-eslint/await-thenable
  const result = await dialog.showOpenDialog({
    properties: ["openFile"],
    filters: [
      {
        name: "Video Files",
        extensions: ["mp4"],
      },
    ],
    title: "Select a video file",
  });

  // @ts-ignore - Suppress TypeScript error
  if (!result.canceled && result.filePaths.length > 0) {
    // @ts-ignore - Suppress TypeScript error
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
    console.error("ファイル情報取得中のエラー：", error);
    return null;
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
        title: "Save processed video",
      });

      // @ts-ignore - Suppress TypeScript error
      if (!result.canceled && result.filePath) {
        let bufferToWrite;

        if (Array.isArray(fileData.fileData)) {
          bufferToWrite = Buffer.from(fileData.fileData);
        } else if (fileData.fileData instanceof Uint8Array) {
          bufferToWrite = Buffer.from(fileData.fileData);
        } else if (Buffer.isBuffer(fileData.fileData)) {
          bufferToWrite = fileData.fileData;
        } else {
          bufferToWrite = Buffer.from(fileData.fileData);
        }

        // @ts-ignore - Suppress TypeScript error
        fs.writeFileSync(result.filePath, bufferToWrite);
        // @ts-ignore - Suppress TypeScript error
        return { success: true, path: result.filePath };
      }

      return { success: false };
    } catch (error) {
      console.error("=== DOWNLOAD ERROR ===");
      console.error("Error details:", error);
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
      console.error("Socket error:", error);
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

async function sendFileData(
  socket: net.Socket,
  filePath: string,
  requestParams: any,
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
        console.error("動画データ送信中のエラー：", error);
        reject(error);
      });
    } catch (error) {
      console.error("動画データ送信中のエラー：", error);
      reject(error);
    }
  });
}

async function receiveResponse(socket: net.Socket): Promise<any> {
  return new Promise((resolve, reject) => {
    let buffer = Buffer.alloc(0);
    let headerReceived = false;
    let responseCode: number;
    let dataSize: number;
    let totalDataReceived = 0;
    let successJson: any = null;
    let fileData = Buffer.alloc(0);
    let expectingFileData = false;

    socket.on("data", (chunk: Buffer) => {
      buffer = Buffer.concat([buffer, chunk]);

      try {
        if (!headerReceived && buffer.length >= 1) {
          responseCode = buffer.readUInt8(0);

          if (responseCode === 0x00) {
            if (buffer.length >= 5) {
              dataSize = buffer.readUInt32BE(1);
              if (buffer.length >= 5 + dataSize) {
                const errorData = buffer.subarray(5, 5 + dataSize);
                const errorText = errorData.toString("utf-8");
                headerReceived = true;
                resolve({ status: "error", error: errorText });
                return;
              }
            }
          } else {
            if (buffer.length >= 5) {
              dataSize = buffer.readUInt32BE(1);
              if (buffer.length >= 5 + dataSize) {
                const jsonData = buffer.subarray(5, 5 + dataSize);
                successJson = JSON.parse(jsonData.toString("utf-8"));

                buffer = buffer.subarray(5 + dataSize);
                totalDataReceived = 0;
                expectingFileData = true;
                headerReceived = true;

                if (buffer.length > 0) {
                  fileData = Buffer.concat([fileData, buffer]);
                  totalDataReceived += buffer.length;
                  buffer = Buffer.alloc(0);
                }

                if (totalDataReceived >= successJson.file_size) {
                  resolve({
                    status: "success",
                    filename: successJson.file_extension
                      ? `output.${successJson.file_extension}`
                      : "output.mp4",
                    fileData: fileData.subarray(0, successJson.file_size),
                    fileExtension: successJson.file_extension,
                  });
                }
              }
            }
          }
        } else if (headerReceived && expectingFileData) {
          fileData = Buffer.concat([fileData, buffer]);
          totalDataReceived += buffer.length;
          buffer = Buffer.alloc(0);

          if (totalDataReceived >= successJson.file_size) {
            resolve({
              status: "success",
              filename: successJson.file_extension
                ? `output.${successJson.file_extension}`
                : "output.mp4",
              fileData: fileData.subarray(0, successJson.file_size),
              fileExtension: successJson.file_extension,
            });
          }
        }
      } catch (error) {
        console.error("Error processing received data:", error);
        reject(error);
      }
    });

    socket.on("error", (error) => {
      console.error("Socket error during receive:", error);
      reject(error);
    });

    socket.on("close", () => {
      if (!headerReceived) {
        reject(
          new Error("Connection closed before receiving complete response"),
        );
      }
    });
  });
}

async function processVideoRequest(request: ProcessingRequest): Promise<any> {
  const config = loadClientConfig();

  let socket: net.Socket | null = null;

  try {
    socket = await connectToServer(config);

    await sendFileData(socket, request.filePath, request.requestParams, config);

    const response = await receiveResponse(socket);

    if (response.status === "error") {
      throw new Error(response.error);
    }

    const userFileName =
      (request.requestParams as any).outputFileName || "output";
    const finalFileName = `${userFileName}.${response.fileExtension}`;

    return {
      status: "success",
      message: "Video processing completed successfully!",
      filename: finalFileName,
      fileExtension: response.fileExtension,
      fileData: Array.from(response.fileData),
    };
  } catch (error) {
    console.error("=== ERROR PROCESSING VIDEO ===");
    console.error("Error:", error);
    throw error;
  } finally {
    if (socket) {
      socket.destroy();
    }
  }
}

app.whenReady().then(createWindow);

app.on("window-all-closed", () => {
  if (process.platform !== "darwin") app.quit();
});

app.on("activate", () => {
  if (BrowserWindow.getAllWindows().length === 0) {
    createWindow();
  }
});
