# videoCompressor

## 技術要素

- プログラミング言語
  - python 3.11.2
- Python のプロジェクト管理・依存管理・パッケージ管理
  - Poetry
  - Pyenv

## 環境構築

```
# 1. プロジェクトをクローン
git clone <リポジトリURL>
cd videoCompressor

# 2. Pythonバージョンのインストール（必要な場合のみ）
pyenv install 3.11.2

# 3. Poetryのインストール（必要な場合のみ）
curl -sSL https://install.python-poetry.org | python3 -

# 4. 依存パッケージのインストール
poetry install

# 5. スクリプト実行例
poetry run python server/server.py
poetry run python client/client.py
```

ライブラリを新規で追加する場合の手順は以下

```
# 以下のコマンドでライブラリ追加しリモーリポジトリにpush
poetry add <パッケージ名>

# 他開発者はpullした後に以下を実行すれば、追加されたライブラリも自動でインストール
poetry install
```

## ブランチ運用

短期間・少人数の開発のため、以下のように運用する

- 各開発者は、main ブランチから feature ブランチを切る
- feature ブランチ開発後、feature->main に PR を作成し他開発者にレビュー依頼を行う
- レビュー完了後、開発者は feature->main に merge を行う
