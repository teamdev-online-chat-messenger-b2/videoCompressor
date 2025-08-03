import { contextBridge, ipcRenderer } from "electron";

interface FileStats {
  size: number;
  isFile: boolean;
}

interface ElectronAPI {
  openVideoDialog: () => Promise<string | any>;
  getFileStats: (filePath: string) => Promise<FileStats | any>;
  processVideo: (filePath: string, params: any) => Promise<any>;
}

contextBridge.exposeInMainWorld("electronAPI", {
  openVideoDialog: () => ipcRenderer.invoke("open-video-dialog"),
  getFileStats: (filePath: string) =>
    ipcRenderer.invoke("get-file-stats", filePath),
  processVideo: async (filePath: string, params: any) => {
    try {
      const result = await ipcRenderer.invoke("process-video-request", {
        filePath: filePath,
        requestParams: params,
      });

      return result;
    } catch (error) {
      throw error;
    }
  },
} as ElectronAPI);
