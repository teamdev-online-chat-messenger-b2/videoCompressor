
// DOM要素の取得 
const uploadArea = document.getElementById('uploadArea') as HTMLDivElement;
const videoFile = document.getElementById('videoFile') as HTMLInputElement;

// uploadAreaをクリックした時にconsole.logを表示する
uploadArea.addEventListener('click', () => {
  videoFile.click();
});

//ファイルを選択後の処理
videoFile.addEventListener('change', () => {
  const file = videoFile.files?.[0];
  if (file) {
    console.log(file.name);
  }
});