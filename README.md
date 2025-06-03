# OpenAI チャット & 楽天トラベル検索アプリ

Streamlit、OpenAI API、楽天トラベル API を使用したチャット & ホテル検索アプリケーションです。

## 機能

### AI チャット機能

- OpenAI GPT-3.5-turbo を使用したチャット機能
- チャット履歴の表示
- 履歴のクリア機能

### ホテル検索機能

- 楽天トラベル空室検索 API を使用したホテル検索
- 自然言語での検索条件入力
- 詳細検索オプション
- 美しい UI

## セットアップ

### 1. 依存関係のインストール

```bash
pip install -r requirements.txt
```

### 2. 環境変数の設定

プロジェクトルートに `.env` ファイルを作成し、以下の内容を追加してください：

```
# OpenAI API キーを設定してください
# https://platform.openai.com/api-keys から取得できます
OPENAI_API_KEY=your_openai_api_key_here

# 楽天 API キー（Application ID）を設定してください
# https://webservice.rakuten.co.jp/ から取得できます
RAKUTEN_APP_ID=your_rakuten_app_id_here

# Google Geocoding API キー（オプション - 緯度経度の精度向上）
# https://console.cloud.google.com/ から取得できます
GOOGLE_GEOCODING_API_KEY=your_google_geocoding_api_key_here
```

**重要**:

- `your_openai_api_key_here` を実際の OpenAI API キーに置き換えてください
- `your_rakuten_app_id_here` を実際の楽天 Application ID に置き換えてください
- `your_google_geocoding_api_key_here` を実際の Google Geocoding API キーに置き換えてください（オプション）

### 3. API キーの取得方法

#### OpenAI API キー

1. [OpenAI Platform](https://platform.openai.com/api-keys) にアクセス
2. サインアップまたはログイン
3. 「Create new secret key」をクリック
4. 生成された API キーをコピーして `.env` ファイルに貼り付け

#### 楽天 Application ID

1. [楽天ウェブサービス](https://webservice.rakuten.co.jp/) にアクセス
2. 会員登録またはログイン
3. 「アプリ ID 発行」をクリック
4. アプリケーション情報を入力してアプリを作成
5. 発行された Application ID をコピーして `.env` ファイルに貼り付け

#### Google Geocoding API キー（オプション）

Google Geocoding API を使用することで、地名から緯度経度への変換精度が大幅に向上します：

1. [Google Cloud Console](https://console.cloud.google.com/) にアクセス
2. 新しいプロジェクトを作成または既存のプロジェクトを選択
3. 「API とサービス」→「ライブラリ」で「Geocoding API」を有効化
4. 「認証情報」→「認証情報を作成」→「API キー」でキーを作成
5. API キーを制限（Geocoding API のみ使用可能に設定）することを推奨
6. 発行された API キーを `.env` ファイルに貼り付け

**緯度経度精度について：**

- Google Geocoding API 使用時：高精度な位置情報取得
- OpenAI のみ使用時：フォールバック機能として動作
- Google API キーがない場合は自動的に OpenAI を使用

## 使用方法

アプリケーションを起動：

```bash
streamlit run app.py
```

ブラウザが自動的に開き、アプリケーションが表示されます。

## 使い方

### AI チャット

1. 「💬 AI チャット」タブを選択
2. 下部のチャット入力欄に質問や会話を入力
3. Enter キーを押すか Submit ボタンをクリック
4. AI が回答を生成して表示
5. サイドバーの「💬 チャット履歴をクリア」ボタンで履歴をリセット可能

### ホテル検索

1. 「🏨 ホテル検索」タブを選択
2. 自然な文章で検索条件を入力（例：「東京に 12 月 1 日から 1 泊、大人 2 名で泊まれるホテル」）
3. 「🔍 ホテルを検索」ボタンをクリック
4. 検索結果が表示されます

#### 詳細検索オプション

- 「⚙️ 詳細検索オプション」を展開
- チェックイン日、泊数、人数、予算、地域を詳細に設定
- 「詳細検索を実行」ボタンで検索

## 対応している検索条件（自然言語）

### 日付表現

- `12月1日`、`2024-12-01`（具体的な日付）
- `今日`、`明日`、`明後日`（相対的な日付）
- `2泊`、`3泊`（泊数指定）

### 人数表現

- `大人2名`、`大人3人`（大人の人数）
- `子供1名`、`子供2人`（子供の人数）

### 地域表現

- `東京`、`大阪`、`京都`、`沖縄`、`北海道`、`箱根`、`熱海`

### 予算表現

- `10000円以下`、`8500円以下`（最大料金）

## 注意事項

- OpenAI API の使用には料金が発生する場合があります
- 楽天トラベル API の使用にも制限があります（無料枠あり）
- API キーは秘密情報として慎重に管理してください
- `.env` ファイルは Git にコミットしないでください

## トラブルシューティング

### API キーエラーが表示される場合

1. `.env` ファイルが正しく作成されているか確認
2. API キーが正しく設定されているか確認
3. OpenAI アカウントにクレジットが残っているか確認
4. 楽天 Application ID が有効か確認

### 依存関係エラーの場合

```bash
pip install --upgrade streamlit openai python-dotenv requests
```

### ホテル検索で結果が表示されない場合

1. 楽天 Application ID が正しく設定されているか確認
2. 検索条件を変更してみる（日付、地域など）
3. デバッグ用の検索パラメータを確認

## 技術仕様

- **フロントエンド**: Streamlit
- **AI**: OpenAI GPT-3.5-turbo
- **ホテル検索**: 楽天トラベル空室検索 API
- **自然言語処理**: 正規表現による条件抽出
- **レスポンス形式**: JSON（formatVersion=2）

## API 仕様

楽天トラベル空室検索 API の詳細は [こちら](https://webservice.rakuten.co.jp/documentation/vacant-hotel-search) を参照してください。
