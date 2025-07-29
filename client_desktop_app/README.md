# Desktop App Setup Guide

このガイドは、他の開発者が同じ Electron + TypeScript 環境を構築するための手順です。

## 前提条件

### 必要なソフトウェア

- **Node.js** (v16 以上推奨)
- **npm** (Node.js と一緒にインストール)
- **Git**

### Node.js のインストール確認

```bash
node --version
npm --version
```

## セットアップ手順

### 1. リポジトリのクローン

```bash
git clone <repository-url>
cd videoCompressor
```

### 2. Desktop App ディレクトリに移動

```bash
cd client_desktop_app
```

### 3. 依存関係のインストール

```bash
npm install
```

### 4. 初回ビルド

```bash
npm run build
```

### 5. アプリケーションの起動

```bash
npm start
```

## 開発コマンド

### 基本的なコマンド

- `npm start` - アプリケーションをビルドして起動
- `npm run build` - TypeScript ファイルをコンパイル
- `npm run dev` - TypeScript ファイルの変更を監視（コンパイルのみ）

TODO : ホットリロード対応

## プロジェクト構造

```
client_desktop_app/
├── src/
│   ├── main.ts          # Electronメインプロセス
│   └── index.html       # メインウィンドウのHTML
├── dist/                # コンパイル後のファイル（自動生成）
├── package.json         # プロジェクト設定
├── tsconfig.json        # TypeScript設定
└── package-lock.json    # 依存関係のロックファイル
```
