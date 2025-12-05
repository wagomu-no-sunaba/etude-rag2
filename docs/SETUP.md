# etude-rag2 セットアップガイド

このドキュメントでは、etude-rag2 プロジェクトの初期セットアップ手順を説明します。

## 目次

1. [前提条件](#前提条件)
2. [ローカル開発環境のセットアップ](#ローカル開発環境のセットアップ)
3. [GCPプロジェクトのセットアップ](#gcpプロジェクトのセットアップ)
4. [Terraformによるインフラ構築](#terraformによるインフラ構築)
5. [データベースの初期化](#データベースの初期化)
6. [サービスアカウントキーの設定](#サービスアカウントキーの設定)
7. [初回デプロイ](#初回デプロイ)
8. [動作確認](#動作確認)
9. [トラブルシューティング](#トラブルシューティング)

---

## 前提条件

### 必要なツール

| ツール | バージョン | 用途 |
|--------|----------|------|
| Python | 3.12+ | アプリケーション実行 |
| uv | latest | Python パッケージ管理 |
| gcloud CLI | latest | GCP 操作 |
| Terraform | 1.5+ | インフラ構築 |
| Docker | latest | コンテナビルド（ローカル開発用） |
| psql | 15+ | データベース操作 |

### GCPアカウント

- 課金が有効化されたGCPプロジェクト
- オーナーまたは編集者権限

### Google Drive

- RAGソースとなるドキュメントを格納するフォルダ
- フォルダID（URLの `/folders/` 以降の文字列）

---

## ローカル開発環境のセットアップ

### 1. リポジトリのクローン

```bash
git clone https://github.com/wagomu-no-sunaba/etude-rag2.git
cd etude-rag2
```

### 2. Python依存関係のインストール

```bash
uv sync
```

### 3. 環境変数の設定

```bash
cp .env.example .env
```

`.env` ファイルを編集：

```bash
# Google Cloud
GOOGLE_PROJECT_ID=your-project-id
GOOGLE_LOCATION=us-central1
SERVICE_ACCOUNT_FILE=/path/to/service-account.json

# Database (ローカル開発時)
DB_HOST=localhost
DB_PORT=5432
DB_NAME=rag_db
DB_USER=postgres
DB_PASSWORD=your-password

# Google Drive
TARGET_FOLDER_ID=your-folder-id
```

---

## GCPプロジェクトのセットアップ

### 1. gcloud CLIの認証

```bash
# ログイン
gcloud auth login

# プロジェクトの設定
gcloud config set project YOUR_PROJECT_ID

# Application Default Credentials の設定
gcloud auth application-default login
```

### 2. 必要なAPIの有効化

Terraformで自動的に有効化されますが、事前に確認する場合：

```bash
gcloud services enable \
    run.googleapis.com \
    sqladmin.googleapis.com \
    aiplatform.googleapis.com \
    cloudbuild.googleapis.com \
    secretmanager.googleapis.com \
    vpcaccess.googleapis.com \
    artifactregistry.googleapis.com \
    drive.googleapis.com \
    iam.googleapis.com \
    iamcredentials.googleapis.com \
    cloudresourcemanager.googleapis.com
```

---

## Terraformによるインフラ構築

### 1. Terraform変数ファイルの作成

```bash
cd terraform
cp terraform.tfvars.example terraform.tfvars
```

`terraform.tfvars` を編集：

```hcl
# 必須設定
project_id       = "your-gcp-project-id"
github_repo      = "wagomu-no-sunaba/etude-rag2"
target_folder_id = "your-google-drive-folder-id"
my_email         = "your-email@example.com"

# オプション設定（必要に応じて変更）
# region      = "us-central1"
# environment = "dev"
# db_tier     = "db-f1-micro"
```

### 2. Terraformの初期化と適用

```bash
# 初期化
terraform init

# プランの確認
terraform plan

# インフラの作成
terraform apply
```

### 3. 出力値の確認

```bash
terraform output
```

重要な出力値：
- `api_service_url` - API サービスのURL
- `streamlit_service_url` - Streamlit UIのURL
- `cloud_sql_connection_name` - Cloud SQL接続名
- `workload_identity_provider` - GitHub Actions用

---

## データベースの初期化

### 1. Cloud SQL Proxy の設定（ローカルから接続する場合）

```bash
# Cloud SQL Proxy をインストール
curl -o cloud-sql-proxy https://storage.googleapis.com/cloud-sql-connectors/cloud-sql-proxy/v2.8.0/cloud-sql-proxy.darwin.arm64
chmod +x cloud-sql-proxy

# プロキシを起動
./cloud-sql-proxy YOUR_PROJECT_ID:us-central1:etude-rag2-db-dev
```

### 2. データベースパスワードの取得

```bash
gcloud secrets versions access latest \
    --secret="etude-rag2-db-password-dev" \
    --project=YOUR_PROJECT_ID
```

### 3. スキーマの適用

```bash
# Cloud SQL Proxy 経由で接続
psql "host=127.0.0.1 port=5432 dbname=rag_db user=raguser password=YOUR_PASSWORD" \
    < schemas/schema.sql
```

または、Cloud Shell から：

```bash
gcloud sql connect etude-rag2-db-dev --user=raguser --database=rag_db
\i schemas/schema.sql
```

---

## サービスアカウントキーの設定

Google Drive APIを使用するには、サービスアカウントキーが必要です。

### 1. サービスアカウントキーの作成

```bash
# Cloud Run用サービスアカウントのキーを作成
gcloud iam service-accounts keys create sa-key.json \
    --iam-account=etude-rag2-dev@YOUR_PROJECT_ID.iam.gserviceaccount.com
```

### 2. Secret Managerへの登録

```bash
# キーをSecret Managerに登録
gcloud secrets versions add etude-rag2-service-account-key-dev \
    --data-file=sa-key.json \
    --project=YOUR_PROJECT_ID

# ローカルのキーファイルを削除
rm sa-key.json
```

### 3. Google Driveフォルダの共有

サービスアカウントのメールアドレスに、Google Driveフォルダの閲覧権限を付与：

1. Google Driveでフォルダを開く
2. 「共有」をクリック
3. `etude-rag2-dev@YOUR_PROJECT_ID.iam.gserviceaccount.com` を追加
4. 「閲覧者」権限を付与

---

## 初回デプロイ

### 1. ベースイメージのビルド

```bash
./scripts/build-base-images.sh
```

### 2. 全サービスのデプロイ

```bash
./scripts/deploy-all.sh --include-ingester
```

### 3. デプロイ結果の確認

```bash
# サービスURLの確認
gcloud run services describe etude-rag2-api-dev --region=us-central1 --format="value(status.url)"
gcloud run services describe etude-rag2-streamlit-dev --region=us-central1 --format="value(status.url)"
```

---

## 動作確認

### 1. APIヘルスチェック

```bash
curl https://YOUR_API_URL/health
```

期待されるレスポンス：

```json
{"status": "healthy"}
```

### 2. Streamlit UIへのアクセス

ブラウザで Streamlit のURLを開き、UIが表示されることを確認。

### 3. データ取り込みジョブの実行

```bash
gcloud run jobs execute etude-rag2-ingester-dev --region=us-central1
```

ジョブの状態確認：

```bash
gcloud run jobs executions list --job=etude-rag2-ingester-dev --region=us-central1
```

---

## GitHub Actions の設定（CI/CD）

### 1. シークレットの設定

GitHubリポジトリの Settings > Secrets and variables > Actions で以下を設定：

| シークレット名 | 値の取得方法 |
|--------------|-------------|
| `GCP_PROJECT_ID` | プロジェクトID |
| `GCP_REGION` | `us-central1` |
| `WORKLOAD_IDENTITY_PROVIDER` | `terraform output workload_identity_provider` |
| `DEPLOY_SERVICE_ACCOUNT` | `terraform output deploy_service_account_email` |

### 2. ワークフローの確認

`.github/workflows/` ディレクトリにワークフローファイルがあることを確認。

---

## 運用スクリプト

### サービスの一時停止（費用削減）

```bash
./scripts/pause-infra.sh
```

### サービスの再開

```bash
./scripts/resume-infra.sh
```

### 全リソースの削除

```bash
./scripts/destroy-infra.sh
```

---

## トラブルシューティング

### Cloud Run サービスが起動しない

1. ログを確認：
```bash
gcloud run services logs read etude-rag2-api-dev --region=us-central1 --limit=50
```

2. よくある原因：
   - データベースへの接続エラー → VPC Connectorの確認
   - シークレットアクセスエラー → IAM権限の確認
   - イメージプルエラー → Artifact Registryの確認

### Cloud SQL に接続できない

1. VPC Connectorの状態確認：
```bash
gcloud compute networks vpc-access connectors describe etude-rag2-vpc-dev --region=us-central1
```

2. Private IP が設定されているか確認：
```bash
gcloud sql instances describe etude-rag2-db-dev --format="value(ipAddresses)"
```

### Ingester ジョブが失敗する

1. ジョブのログを確認：
```bash
gcloud run jobs executions describe EXECUTION_NAME \
    --job=etude-rag2-ingester-dev \
    --region=us-central1
```

2. よくある原因：
   - サービスアカウントキーが設定されていない
   - Google Driveフォルダの共有設定が不足
   - タイムアウト（大量ドキュメントの場合）

### Terraform apply でエラー

1. 既存リソースとの競合：
```bash
terraform import google_xxx.yyy RESOURCE_ID
```

2. API有効化の待機：
   - 一部のAPIは有効化に時間がかかる
   - 数分待ってから再実行

---

## 次のステップ

- [RAG_SYSTEM_BLUEPRINT.md](./RAG_SYSTEM_BLUEPRINT.md) - システム設計の詳細
- [IMPLEMENTATION_PLAN.md](./IMPLEMENTATION_PLAN.md) - 実装計画
- [CLAUDE.md](../CLAUDE.md) - 開発ガイドライン
