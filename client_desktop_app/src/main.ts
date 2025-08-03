import {
  app,
  BrowserWindow,
  ipcMain,
  dialog,
  OpenDialogReturnValue,
} from "electron";
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

  console.log("Dialog result:", result);
  console.log("Result type:", typeof result);
  console.log("Has canceled property:", "canceled" in result);

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

function loadClientConfig(): ServerConfig {
  try {
    const configPath = path.join(__dirname, "..", "..", "config.json");

    const configData = fs.readFileSync(configPath, "utf-8");
    const config = JSON.parse(configData);

    console.log("コンフィグ：", config);

    return {
      server_address: config.server_address,
      server_port: config.server_port,
      stream_rate: config.stream_rate,
    };
  } catch (error) {
    throw error;
  }
}

ipcMain.handle(
  "process-video-request",
  async (event, request: ProcessingRequest) => {
    try {
      await new Promise((resolve) => setTimeout(resolve, 20000));

      const testResponse = {
        status: "success",
        message: "Communication test successful!",
        filename: "test_output.mp4",
        originalFile: request.filePath,
        action: request.requestParams.action,
      };

      return testResponse;
    } catch (error) {
      throw error;
    }
  },
);

app.whenReady().then(createWindow);

app.on("window-all-closed", () => {
  if (process.platform !== "darwin") app.quit();
});
