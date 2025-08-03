interface ProcessingParams {
  action: number;
  resolution?: string;
  aspect_ratio?: string;
  startseconds?: number;
  endseconds?: number;
  extension?: string;
}

interface SelectedFile {
  path: string;
  name: string;
  size: number;
}

class VideoProcessorUI {
  private selectedFile: SelectedFile | null = null;
  private selectedOperation: string | null = null;
  private processingParams: ProcessingParams | null = null;

  constructor() {
    this.initializeEventListeners();
  }

  private initializeEventListeners(): void {
    this.setupFileUpload();

    // 処理モードカードを有効にしてからの処理
    this.setupOperationSelection();

    //　選択された処理モードに応じてsetting-groupを表示し、実行ボタンを有効にした後の処理
    this.setupExecuteButton();
  }

  private async setupFileUpload(): Promise<void> {
    const uploadArea = document.getElementById("uploadArea") as HTMLDivElement;
    const fileInfo = document.getElementById("fileInfo") as HTMLDivElement;
    const fileName = document.getElementById(
      "fileName",
    ) as HTMLParagraphElement;

    uploadArea.addEventListener("click", async () => {
      try {
        const filePath = await (window as any).electronAPI.openVideoDialog();

        if (filePath) {
          console.log("選択されたファイルパス：", filePath);

          const fileStats = await (window as any).electronAPI.getFileStats(
            filePath,
          );

          if (!fileStats) {
            alert("ファイル情報を取得できませんでした");
            return;
          }

          const maxSize = Math.pow(2, 40);
          if (fileStats.size > maxSize) {
            alert("処理対象の動画ファイルは1TB以下です。");
            return;
          }

          const selectedFileName = filePath.split(/[\\/]/).pop() || "Unknown";

          this.selectedFile = {
            path: filePath,
            name: selectedFileName,
            size: fileStats.size,
          };

          fileName.textContent = `${selectedFileName} (${this.formatFileSize(fileStats.size)})`;

          fileInfo.classList.remove("hidden");

          this.enableOperationSelection();
        } else {
          console.log("ファイルが選択されていません");
        }
      } catch (error) {
        console.error("ファイルが選択中のエラー：", error);
      }
    });
  }

  // handleFileSelection内で使用
  private formatFileSize(bytes: number): string {
    const sizes = ["Bytes", "KB", "MB", "GB", "TB"];
    // 本当は1024をベースとしたlogを実行したいが、log_n(x) = log(x) / log (n)という数学プロパティを利用する
    const i = Math.floor(Math.log(bytes) / Math.log(1024));
    return parseFloat((bytes / Math.pow(1024, i)).toFixed(2)) + " " + sizes[i];
  }

  // handleFileSelection内で使用
  private enableOperationSelection(): void {
    const operationCards = document.querySelectorAll(".operation-card");
    operationCards.forEach((card) => {
      // 処理モードカードからdisabledプロパティを削除する
      card.classList.remove("disabled");
    });
  }

  private setupOperationSelection(): void {
    const operationCards = document.querySelectorAll(".operation-card");
    const settingsSection = document.getElementById(
      "settingsSection",
    ) as HTMLElement;

    operationCards.forEach((card) => {
      card.addEventListener("click", () => {
        if (!this.selectedFile) {
          alert("まず動画ファイルを選択してください");
          return;
        }

        // クリックを感知したら一回全てのカードのselectedプロパティを削除し、このカードには追加する
        operationCards.forEach((c) => c.classList.remove("selected"));
        card.classList.add("selected");

        // selectedOperationをセットする（compress, resolution, aspect, audio, gif）
        this.selectedOperation = card.getAttribute("data-operation")!;

        // セッティングセクションを表示する
        settingsSection.classList.remove("hidden");

        // 選択された処理モードに応じてsetting-groupを表示する
        this.showRelevantSettings(this.selectedOperation);

        // 実行ボタンを有効にする
        this.updateExecuteButton();
      });
    });
  }

  // setupOperationSelection内で使用
  private showRelevantSettings(operation: string): void {
    // settings-section内にあるsetting-group divを隠す
    const settingGroups = document.querySelectorAll(".setting-group");
    settingGroups.forEach((group) => group.classList.add("hidden"));

    // 選択された処理モードに応じてsetting-groupをidを仕様し表示する
    switch (operation) {
      case "resolution":
        document
          .getElementById("resolutionSettings")
          ?.classList.remove("hidden");
        break;
      case "aspect":
        document.getElementById("aspectSettings")?.classList.remove("hidden");
        break;
      case "gif":
        document.getElementById("gifSettings")?.classList.remove("hidden");
        break;
    }

    document.getElementById("outputSettings")?.classList.remove("hidden");
  }

  // setupOperationSelection内で使用
  private updateExecuteButton(): void {
    const executeBtn = document.getElementById(
      "executeBtn",
    ) as HTMLButtonElement;
    // ファイルがセットされモードを選択されている場合クリックできるにする
    if (this.selectedFile && this.selectedOperation) {
      executeBtn.disabled = false;
      executeBtn.textContent = "🚀 変換を実行";
    }
  }

  private setupExecuteButton(): void {
    const executeBtn = document.getElementById(
      "executeBtn",
    ) as HTMLButtonElement;

    executeBtn.addEventListener("click", async () => {
      if (!this.selectedFile || !this.selectedOperation) {
        alert("ファイルと操作を選択してください");
        return;
      }

      // パラメターを取得
      this.processingParams = this.collectProcessingParams();

      if (!this.processingParams) {
        return; // Validation failed
      }

      console.log("パラメターを送信:", this.processingParams);
      console.log("選択されたファイル:", this.selectedFile);

      // プログレスを表示
      this.showProgressSection();

      try {
        // main.tsに対してpreload.tsのAPIを通じて処理を依頼する
        const result = await (window as any).electronAPI.processVideo(
          this.selectedFile.path,
          this.processingParams,
        );

        console.log("レスポンスを受信:", result);
        this.handleProcessingSuccess(result);
      } catch (error) {
        console.error("プロセス中エラー:", error);
        this.handleProcessingError(error);
      }
    });
  }

  private collectProcessingParams(): ProcessingParams | null {
    const action = this.getActionNumber(this.selectedOperation!);
    const params: ProcessingParams = {
      action: action,
    };

    switch (this.selectedOperation) {
      case "compress":
        break;

      case "resolution":
        const resolutionSelect = document.getElementById(
          "resolutionSelect",
        ) as HTMLSelectElement;
        params.resolution = resolutionSelect.value;
        break;

      case "aspect":
        const aspectSelect = document.getElementById(
          "aspectRatio",
        ) as HTMLSelectElement;
        params.aspect_ratio = aspectSelect.value;
        break;

      case "audio":
        break;

      case "gif":
        const startTime = (
          document.getElementById("startTime") as HTMLInputElement
        ).value;
        const endTime = (document.getElementById("endTime") as HTMLInputElement)
          .value;
        const format = (
          document.getElementById("outputFormat") as HTMLSelectElement
        ).value;

        if (!startTime || !endTime) {
          alert("開始時間と終了時間を入力してください");
          return null;
        }

        params.startseconds = this.timeToSeconds(startTime);
        params.endseconds = this.timeToSeconds(endTime);
        params.extension = format;

        if (params.startseconds >= params.endseconds) {
          alert("終了時刻は開始時刻より後にしてください");
          return null;
        }
        break;
    }

    return params;
  }

  private getActionNumber(operation: string): number {
    // Mapを使用し処理モードに応じてnumberを返す
    const actionMap: { [key: string]: number } = {
      compress: 1,
      resolution: 2,
      aspect: 3,
      audio: 4,
      gif: 5,
    };
    return actionMap[operation];
  }

  private timeToSeconds(timeStr: string): number {
    const parts = timeStr.split(":").map(Number);
    if (parts.length === 2) {
      return parts[0] * 60 + parts[1];
    } else if (parts.length === 3) {
      return parts[0] * 3600 + parts[1] * 60 + parts[2];
    }
    return 0;
  }

  private showProgressSection(): void {
    // 他のセクションを全て隠す
    document.querySelector(".upload-section")?.classList.add("hidden");
    document.querySelector(".operation-section")?.classList.add("hidden");
    document.querySelector(".settings-section")?.classList.add("hidden");
    document.querySelector(".execute-section")?.classList.add("hidden");

    // プログレスセクションを表示する
    const progressSection = document.getElementById("progressSection");
    progressSection?.classList.remove("hidden");

    // animateProgressを呼び出しプロクレスを開始する
    this.animateProgress();
  }

  private animateProgress(): void {
    const progressFill = document.getElementById("progressFill") as HTMLElement;
    const progressText = document.getElementById("progressText") as HTMLElement;

    let progress = 0;
    const interval = setInterval(() => {
      progress += Math.random() * 10;
      if (progress > 90) progress = 90;

      progressFill.style.width = `${progress}%`;
      progressText.textContent = `処理中... ${Math.round(progress)}%`;
    }, 500);

    // 後でインターバルをを削除するようにIDをセットする
    (this as any).progressInterval = interval;
  }

  private handleProcessingSuccess(result: any): void {
    // Complete progress
    if ((this as any).progressInterval) {
      clearInterval((this as any).progressInterval);
    }

    const progressFill = document.getElementById("progressFill") as HTMLElement;
    const progressText = document.getElementById("progressText") as HTMLElement;
    progressFill.style.width = "100%";
    progressText.textContent = "処理完了！";

    // Show result section after a brief delay
    setTimeout(() => {
      this.showResultSection(result);
    }, 1000);
  }

  private handleProcessingError(error: any): void {
    // Clear progress animation
    if ((this as any).progressInterval) {
      clearInterval((this as any).progressInterval);
    }

    console.error("Processing error:", error);
    alert(`処理中にエラーが発生しました: ${error.message || error}`);

    // Reset UI
    this.resetUI();
  }

  private showResultSection(result: any): void {
    const progressSection = document.getElementById("progressSection");
    const resultSection = document.getElementById("resultSection");
    const resultMessage = document.getElementById("resultMessage");

    progressSection?.classList.add("hidden");
    resultSection?.classList.remove("hidden");

    if (resultMessage) {
      resultMessage.textContent = `変換が完了しました！ファイル: ${result.filename || "処理済みファイル"}`;
    }

    // Setup download button
    this.setupDownloadButton(result);
  }

  private setupDownloadButton(result: any): void {
    const downloadBtn = document.getElementById("downloadBtn");
    downloadBtn?.addEventListener("click", () => {
      // This will be handled by the main process
      (window as any).electronAPI.downloadFile(result);
    });
  }

  private resetUI(): void {
    // Show original sections
    document.querySelector(".upload-section")?.classList.remove("hidden");
    document.querySelector(".operation-section")?.classList.remove("hidden");
    document.querySelector(".execute-section")?.classList.remove("hidden");

    // Hide progress and result sections
    document.getElementById("progressSection")?.classList.add("hidden");
    document.getElementById("resultSection")?.classList.add("hidden");
  }
}

// Initialize the UI when the DOM is loaded
document.addEventListener("DOMContentLoaded", () => {
  new VideoProcessorUI();
});

// Add CSS for selected state and drag-over effect
const style = document.createElement("style");
style.textContent = `
  .operation-card.selected {
    border: 2px solid #007bff;
    background-color: #e3f2fd;
  }

  .upload-area.drag-over {
    border-color: #007bff;
    background-color: #f0f8ff;
  }

  .operation-card.disabled {
    opacity: 0.5;
    pointer-events: none;
  }

  .hidden {
    display: none !important;
  }
`;
document.head.appendChild(style);
