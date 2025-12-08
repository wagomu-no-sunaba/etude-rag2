# etude-rag2 セットアップガイド

このドキュメントでは、etude-rag2 プロジェクトを**ゼロから本番環境まで**構築する完全な手順を説明します。

## 目次

1. [クイックスタート（所要時間の目安）](#クイックスタート所要時間の目安)
2. [前提条件](#前提条件)
3. [Step 1: ローカル開発環境のセットアップ](#step-1-ローカル開発環境のセットアップ)
4. [Step 2: GCP プロジェクトの作成](#step-2-gcp-プロジェクトの作成)
5. [Step 3: Terraform による環境変数とインフラ構築](#step-3-terraform-による環境変数とインフラ構築)
6. [Step 4: データベースの初期化](#step-4-データベースの初期化)
7. [Step 5: Google Drive の設定](#step-5-google-drive-の設定)
8. [Step 6: ローカル環境の最終設定](#step-6-ローカル環境の最終設定)
9. [Step 7: 動作確認](#step-7-動作確認)
10. [Step 8: GitHub Actions CI/CD の設定](#step-8-github-actions-cicd-の設定)
11. [運用コマンド集](#運用コマンド集)
12. [トラブルシューティング](#トラブルシューティング)

---

## クイックスタート（所要時間の目安）

| ステップ | 所要時間 | 説明 |
|----------|----------|------|
| Step 1 | 5分 | ローカル環境の準備 |
| Step 2 | 5分 | GCPプロジェクト作成 |
| Step 3 | 30-40分 | Terraform でインフラ構築 + イメージビルド |
| Step 4 | 5分 | DB スキーマ適用 |
| Step 5 | 3分 | Google Drive 共有設定 |
| Step 6 | 2分 | ローカル .env 生成 |
| Step 7 | 5分 | 動作確認 |
| **合計** | **約55-65分** | |

---

## 前提条件

### 必要なツール

以下のツールを事前にインストールしてください。

```bash
# バージョン確認コマンド
python --version    # 3.12 以上
uv --version        # 最新版
gcloud --version    # Google Cloud SDK
terraform --version # 1.5 以上
docker --version    # Docker Desktop（ローカルテスト用）
psql --version      # PostgreSQL 15 以上（CLI のみでOK）
```

### インストールリンク

| ツール | インストール方法 |
|--------|-----------------|
| Python 3.12+ | [python.org](https://www.python.org/downloads/) |
| uv | `curl -LsSf https://astral.sh/uv/install.sh \| sh` |
| gcloud CLI | [cloud.google.com/sdk](https://cloud.google.com/sdk/docs/install) |
| Terraform | [terraform.io](https://developer.hashicorp.com/terraform/downloads) |
| Docker | [docker.com](https://www.docker.com/products/docker-desktop) |
| psql | `brew install postgresql` (macOS) |

### GCP アカウント要件

- Google Cloud アカウント
- 請求先アカウント（Billing Account）が有効であること
- オーナーまたは編集者権限

### Google Drive

- RAG ソースとなるドキュメントを格納するフォルダを用意
- フォルダ ID（URL の `/folders/` 以降の文字列）をメモ

---

## Step 1: ローカル開発環境のセットアップ

### 1.1 リポジトリのクローン

```bash
git clone https://github.com/wagomu-no-sunaba/etude-rag2.git
cd etude-rag2
```

### 1.2 Python 依存関係のインストール

```bash
uv sync
```

> uv が自動的に `.venv` を作成し、必要なパッケージをインストールします。

### 1.3 確認

```bash
# 仮想環境が有効化されていることを確認
uv run python --version
```

---

## Step 2: GCP プロジェクトの作成

### 2.1 gcloud CLI の認証

```bash
# Google アカウントでログイン
gcloud auth login

# Application Default Credentials の設定（Terraform で使用）
gcloud auth application-default login
```

### 2.2 プロジェクト作成（自動スクリプト推奨）

```bash
# 請求先アカウント ID を確認
gcloud billing accounts list

# プロジェクト作成スクリプトを実行
./scripts/setup-gcp-project.sh YOUR_PROJECT_ID YOUR_BILLING_ACCOUNT_ID

# 例:
./scripts/setup-gcp-project.sh etude-rag2-dev 012345-ABCDEF-GHIJKL
```

スクリプトが実行する内容：
- ✅ GCP プロジェクトの作成（または既存プロジェクトの使用確認）
- ✅ 請求先アカウントのリンク
- ✅ 必須 API の有効化（cloudresourcemanager, serviceusage, iam, servicenetworking）
- ✅ Application Default Credentials の設定
- ✅ `terraform/terraform.tfvars` テンプレートの生成

### 2.3 （代替）手動でプロジェクト作成

```bash
# プロジェクト作成
gcloud projects create YOUR_PROJECT_ID --name="etude-rag2"

# 現在のプロジェクトに設定
gcloud config set project YOUR_PROJECT_ID

# 請求先アカウントをリンク
gcloud billing projects link YOUR_PROJECT_ID --billing-account=YOUR_BILLING_ACCOUNT_ID
```

---

## Step 3: Terraform による環境変数とインフラ構築

### 3.1 terraform.tfvars の編集

```bash
cd terraform

# スクリプトで生成されたファイルを確認・編集
# または手動でテンプレートからコピー
cp terraform.tfvars.example terraform.tfvars
```

`terraform.tfvars` を編集：

```hcl
# ===========================================
# 必須設定（必ず変更してください）
# ===========================================

# GCP プロジェクト ID
project_id = "your-gcp-project-id"

# GitHub リポジトリ（owner/repo 形式）
github_repo = "your-org/etude-rag2"

# Google Drive フォルダ ID（RAG ソースの格納先）
target_folder_id = "1ABCdefGHIjklMNOpqrSTUvwxYZ"

# あなたのメールアドレス（ACL フィルタリング用）
my_email = "your-email@example.com"

# ===========================================
# オプション設定（デフォルト値で通常OK）
# ===========================================

# region      = "us-central1"
# environment = "dev"
# db_tier     = "db-f1-micro"  # 本番では "db-custom-2-7680" など推奨
```

### 3.2 Terraform の初期化

```bash
# terraform ディレクトリ内で実行
terraform init
```

出力例：
```
Terraform has been successfully initialized!
```

### 3.3 プランの確認

```bash
terraform plan
```

> 作成されるリソースを確認します。エラーが出た場合は `terraform.tfvars` を確認してください。

### 3.4 インフラの作成（第1段階：基盤リソース、約15-20分）

Cloud Run以外の基盤リソースを先に作成します（Cloud Runはコンテナイメージが必要なため後で作成）：

```bash
terraform apply -target=google_project_service.services \
  -target=google_artifact_registry_repository.repo \
  -target=google_compute_network.vpc \
  -target=google_compute_global_address.private_ip \
  -target=google_service_networking_connection.private_vpc_connection \
  -target=google_sql_database_instance.postgres \
  -target=google_sql_database.database \
  -target=google_sql_user.user \
  -target=google_secret_manager_secret.db_password \
  -target=google_secret_manager_secret_version.db_password \
  -target=google_vpc_access_connector.connector \
  -target=google_service_account.cloud_run \
  -target=google_service_account.deploy
```

`yes` と入力して実行を確認します。

**作成されるリソース（第1段階）：**
- Cloud SQL（PostgreSQL + pgvector + pg_trgm）
- Artifact Registry（Docker イメージ保存）
- VPC Connector（Cloud SQL 接続用）
- Secret Manager シークレット
- Service Account × 2

### 3.5 コンテナイメージのビルド・プッシュ

Artifact Registry へ認証してイメージをビルドします：

```bash
# プロジェクトルートに戻る
cd ..

# Docker認証
gcloud auth configure-docker us-central1-docker.pkg.dev

# ベースイメージのビルド（初回は約5-10分）
./scripts/build-base-images.sh

# 各サービスのイメージをビルド・プッシュ
./scripts/deploy-all.sh --include-ingester
```

> ベースイメージには Python 依存関係と BGE Reranker モデルが含まれます。

### 3.6 インフラの作成（第2段階：全リソース）

Cloud Run を含む全リソースを作成します：

```bash
cd terraform
terraform apply
```

**作成されるリソース（第2段階で追加）：**
- Cloud Run サービス × 2（API、Streamlit UI）
- Cloud Run ジョブ × 1（Ingester）
- Workload Identity Pool（GitHub Actions 用）

### 3.7 出力値の確認

```bash
terraform output
```

重要な出力値：
```
api_service_url            = "https://etude-rag2-api-dev-xxx.run.app"
streamlit_service_url      = "https://etude-rag2-streamlit-dev-xxx.run.app"
cloud_sql_connection_name  = "project:us-central1:etude-rag2-db-dev"
workload_identity_provider = "projects/xxx/locations/global/workloadIdentityPools/..."
```

---

## Step 4: データベースの初期化

### 4.1 自動スクリプトでスキーマを適用（推奨）

ローカルマシンから自動でスキーマを適用するスクリプトを用意しています：

```bash
# プロジェクトルートで実行
./scripts/apply-schema.sh dev
```

このスクリプトは以下を自動的に行います：
1. Cloud SQL インスタンスのパブリック IP を一時的に有効化
2. 現在の IP アドレスを許可リストに追加
3. Secret Manager からパスワードを取得
4. スキーマを適用
5. テーブル作成を確認
6. パブリック IP を無効化（セキュリティのため）

> **Note**: psql がインストールされている必要があります（`brew install postgresql` など）

### 4.2 手動でスキーマを適用（Cloud Shell 経由）

自動スクリプトが使えない場合は、GCP Cloud Shell から手動で適用できます。

#### 4.2.1 Cloud Shell を開く

1. [GCP Console](https://console.cloud.google.com/) にアクセス
2. 右上の Cloud Shell アイコン（`>_`）をクリック
3. Cloud Shell ターミナルが起動するのを待つ

または、直接 URL でアクセス：
```
https://console.cloud.google.com/?cloudshell=true&project=YOUR_PROJECT_ID
```

#### 4.2.2 パブリック IP を有効化

Cloud SQL はプライベート IP のみで構成されているため、一時的にパブリック IP を有効化します：

```bash
# プロジェクトを設定
gcloud config set project etude-rag2

# パブリック IP を有効化（数分かかります）
gcloud sql instances patch etude-rag2-db-dev --assign-ip
```

#### 4.2.3 リポジトリのクローンとパスワード取得

```bash
# リポジトリをクローン
git clone https://github.com/wagomu-no-sunaba/etude-rag2.git
cd etude-rag2

# データベースパスワードを取得して確認
gcloud secrets versions access latest --secret=etude-rag2-db-password-dev
# （この値を後で入力します）
```

#### 4.2.4 スキーマの適用

```bash
# gcloud sql connect で接続
# パスワードを聞かれたら、上で取得した値を入力
gcloud sql connect etude-rag2-db-dev --user=raguser --database=rag_db
```

接続後、psql プロンプトで以下を実行：

```sql
-- スキーマファイルを読み込み
\i schemas/schema.sql

-- テーブルが作成されたか確認
\dt

-- 終了
\q
```

#### 4.2.5 パブリック IP を無効化（重要）

セキュリティのため、パブリック IP を無効化します：

```bash
gcloud sql instances patch etude-rag2-db-dev --no-assign-ip
```

#### 4.2.6 クリーンアップ

```bash
# （任意）クローンしたリポジトリを削除
cd ~
rm -rf etude-rag2
```

### 参考: 接続情報の確認方法

ローカルの terraform ディレクトリで接続情報を確認できます：

```bash
cd terraform

# 接続文字列
terraform output cloud_sql_connection_name
# 出力例: etude-rag2:us-central1:etude-rag2-db-dev

# データベース接続情報
terraform output db_name        # rag_db
terraform output db_user        # raguser
terraform output db_private_ip  # 10.x.x.x（VPC 内部 IP）

# パスワードのシークレット ID
terraform output db_password_secret_id
# 出力例: etude-rag2-db-password-dev
```

---

## Step 5: Google Drive の設定

### 5.1 サービスアカウントのメールアドレスを確認

```bash
# Terraform output から確認
cd terraform
terraform output cloud_run_service_account_email
```

出力例：
```
"etude-rag2-dev@YOUR_PROJECT_ID.iam.gserviceaccount.com"
```

### 5.2 Google Drive フォルダの共有

1. Google Drive でドキュメントフォルダを開く
2. フォルダ名の横にある「共有」ボタンをクリック
3. 上記のサービスアカウントメールアドレスを追加
4. **「閲覧者」**権限を付与
5. 「送信」をクリック

> サービスアカウントへのメール通知は不要のため、「通知を送信」はオフでOKです。

---

## Step 6: ローカル環境の最終設定

### 6.1 .env ファイルの自動生成

```bash
# プロジェクトルートに戻る
cd ..

# Secret Manager から .env を生成
./scripts/sync-env-from-secrets.sh dev
```

生成される `.env` ファイル例：
```bash
# Generated from Secret Manager - DO NOT EDIT MANUALLY
GOOGLE_PROJECT_ID=your-project-id
GOOGLE_LOCATION=us-central1
ENVIRONMENT=dev
DB_HOST=localhost
DB_PORT=5432
DB_NAME=rag_db
DB_USER=raguser
DB_PASSWORD=xxxxx
TARGET_FOLDER_ID=1ABCdefGHI...
...
```

### 6.2 ローカルでの動作確認

```bash
# Cloud SQL Proxy が起動していることを確認

# API サーバー起動
uv run uvicorn src.api.main:app --reload --port 8000

# 別ターミナルで Streamlit UI 起動
uv run streamlit run src/ui/app.py
```

- API: http://localhost:8000
- API Docs: http://localhost:8000/docs
- Streamlit UI: http://localhost:8501

---

## Step 7: 動作確認

### 7.1 API ヘルスチェック

```bash
curl https://YOUR_API_URL/health
```

期待されるレスポンス：
```json
{"status": "ok"}
```

### 7.2 Streamlit UI へのアクセス

ブラウザで Streamlit の URL を開き、UI が表示されることを確認します。

### 7.3 データ取り込みジョブの実行

```bash
# Ingester ジョブを手動実行
gcloud run jobs execute etude-rag2-ingester-dev --region=us-central1

# 実行状態の確認
gcloud run jobs executions list --job=etude-rag2-ingester-dev --region=us-central1
```

### 7.4 検索機能のテスト

```bash
curl -X POST https://YOUR_API_URL/search \
    -H "Content-Type: application/json" \
    -d '{"query": "テスト検索", "k": 5}'
```

---

## Step 8: GitHub Actions CI/CD の設定

### 8.1 Terraform 出力値の取得

```bash
cd terraform
terraform output github_actions_config
```

出力例：
```
{
  "GCP_PROJECT_ID" = "your-project-id"
  "GCP_REGION" = "us-central1"
  "WORKLOAD_IDENTITY_PROVIDER" = "projects/xxx/locations/global/..."
  "DEPLOY_SERVICE_ACCOUNT" = "etude-rag2-deploy@your-project.iam.gserviceaccount.com"
  "ARTIFACT_REGISTRY" = "us-central1-docker.pkg.dev/your-project/etude-rag2"
}
```

### 8.2 GitHub Secrets の設定

GitHub リポジトリの **Settings > Secrets and variables > Actions** で以下を設定：

| シークレット名 | 設定値 |
|--------------|--------|
| `GCP_PROJECT_ID` | プロジェクト ID |
| `GCP_REGION` | `us-central1` |
| `WORKLOAD_IDENTITY_PROVIDER` | `terraform output workload_identity_provider` の値 |
| `DEPLOY_SERVICE_ACCOUNT` | `terraform output deploy_service_account_email` の値 |

### 8.3 ワークフローの確認

`.github/workflows/` ディレクトリにワークフローファイルがあることを確認。
push 時に自動的にビルド・デプロイが実行されます。

---

## 運用コマンド集

### 日常運用

```bash
# サービスのログ確認
gcloud run services logs read etude-rag2-api-dev --region=us-central1 --limit=50

# Ingester ジョブの手動実行
gcloud run jobs execute etude-rag2-ingester-dev --region=us-central1
```

### データベース接続（Cloud Shell 経由・推奨）

Cloud SQL はプライベート IP のみで構成されているため、**Cloud Shell** からの接続を推奨します。

```bash
# 1. Cloud Shell を開く
# https://console.cloud.google.com/?cloudshell=true&project=etude-rag2

# 2. Cloud Shell 内で実行
gcloud config set project etude-rag2

# 3. パスワードを環境変数に設定
export DB_PASSWORD=$(gcloud secrets versions access latest --secret=etude-rag2-db-password-dev)

# 4. Cloud SQL Proxy を起動（バックグラウンド）
curl -o cloud-sql-proxy https://storage.googleapis.com/cloud-sql-connectors/cloud-sql-proxy/v2.8.0/cloud-sql-proxy.linux.amd64
chmod +x cloud-sql-proxy
./cloud-sql-proxy etude-rag2:us-central1:etude-rag2-db-dev --private-ip --port=5432 &
sleep 3

# 5. 接続
PGPASSWORD=$DB_PASSWORD psql -h 127.0.0.1 -p 5432 -U raguser -d rag_db
```

### 接続情報の確認（ローカル）

```bash
cd terraform
terraform output cloud_sql_connection_name  # 接続文字列
terraform output db_name                     # データベース名
terraform output db_user                     # ユーザー名
terraform output db_password_secret_id       # パスワードシークレット ID
```

### 代替: gcloud sql connect

IAM 認証経由で直接接続する方法（パブリック IP が有効な場合のみ）：

```bash
gcloud sql connect etude-rag2-db-dev --user=raguser --database=rag_db --project=etude-rag2
# パスワードを聞かれたら Secret Manager から取得した値を入力
```

### コスト削減

```bash
# サービスを一時停止（min_instances=0 なら不要）
./scripts/pause-infra.sh

# サービスを再開
./scripts/resume-infra.sh
```

### リソースの完全削除

```bash
# 全リソースを削除（注意：データも削除されます）
./scripts/destroy-infra.sh

# または Terraform で削除
cd terraform
terraform destroy
```

---

## トラブルシューティング

### Terraform apply でエラー

**症状**: API 有効化のエラー

```
Error: Error enabling service: googleapi: Error 403: ...
```

**解決**: 請求先アカウントがリンクされているか確認
```bash
gcloud billing projects describe YOUR_PROJECT_ID
```

---

**症状**: Service Networking API エラー

```
Error: googleapi: Error 403: Service Networking API has not been used in project...
```

**解決**: API を手動で有効化
```bash
gcloud services enable servicenetworking.googleapis.com --project=YOUR_PROJECT_ID
```

> API 有効化後、反映まで 1〜2 分待ってから再実行してください。

---

**症状**: コンテナイメージが見つからないエラー

```
Error: Image 'xxx/api-server:latest' not found.
```

**解決**: Step 3.5 のイメージビルドを実行してから terraform apply を再実行

```bash
# Docker認証
gcloud auth configure-docker us-central1-docker.pkg.dev

# イメージビルド
./scripts/build-base-images.sh
./scripts/deploy-all.sh --include-ingester

# 再度 terraform apply
cd terraform && terraform apply
```

---

**症状**: リソース既存のエラー

```
Error: Error creating Resource: googleapi: Error 409: Resource already exists
```

**解決**: 既存リソースをインポート
```bash
terraform import google_xxx.name RESOURCE_ID
```

---

### Cloud Run サービスが起動しない

**症状**: サービスがヘルスチェックに失敗

```bash
# ログを確認
gcloud run services logs read etude-rag2-api-dev --region=us-central1 --limit=100
```

**よくある原因と解決策**:

| 原因 | 解決策 |
|------|--------|
| DB 接続エラー | VPC Connector の状態を確認 |
| シークレットアクセスエラー | Service Account の IAM 権限を確認 |
| イメージプルエラー | Artifact Registry の認証設定を確認 |

---

### Cloud SQL に接続できない

**症状**: `could not connect to server`

```bash
# VPC Connector の状態確認
gcloud compute networks vpc-access connectors describe etude-rag2-vpc-dev --region=us-central1

# Cloud SQL インスタンスの状態確認
gcloud sql instances describe etude-rag2-db-dev
```

---

### Ingester ジョブが失敗する

**症状**: ジョブがタイムアウトまたはエラー

```bash
# 最新の実行ログを確認
gcloud run jobs executions describe $(gcloud run jobs executions list \
    --job=etude-rag2-ingester-dev \
    --region=us-central1 \
    --limit=1 \
    --format="value(name)") \
    --region=us-central1
```

**よくある原因**:
- Google Drive フォルダの共有設定が不足
- ドキュメント数が多すぎてタイムアウト → `ingester_timeout` を増加

---

## 設定管理アーキテクチャ

本プロジェクトは **Secret Manager を Single Source of Truth** として使用し、設定の二重管理を回避しています。

```
┌─────────────────┐
│ terraform.tfvars│  ────────────┐
└─────────────────┘              │
                                 ▼
                       ┌──────────────────┐
                       │  Secret Manager  │
                       │  (単一の真実源)   │
                       └────────┬─────────┘
                                │
          ┌─────────────────────┼─────────────────────┐
          ▼                     ▼                     ▼
┌─────────────────┐   ┌─────────────────┐   ┌─────────────────┐
│   Cloud Run     │   │  sync-env-from  │   │   config.py     │
│  (本番環境)      │   │  -secrets.sh    │   │  (直接参照)      │
└─────────────────┘   └────────┬────────┘   └─────────────────┘
                               ▼
                     ┌─────────────────┐
                     │     .env        │
                     │ (ローカル開発)   │
                     └─────────────────┘
```

### Secret Manager で管理されるシークレット

| シークレット ID | 管理方法 | 説明 |
|----------------|---------|------|
| `etude-rag2-db-password-{env}` | Terraform (自動生成) | DB パスワード |
| `etude-rag2-drive-folder-id-{env}` | Terraform | Drive フォルダ ID |
| `etude-rag2-my-email-{env}` | Terraform | ACL 用メール |
| `etude-rag2-service-account-key-{env}` | 手動（任意） | SA キー |
| `etude-rag2-app-config-{env}` | Terraform | アプリ設定(JSON) |

---

## 次のステップ

- [RAG_SYSTEM_BLUEPRINT.md](./RAG_SYSTEM_BLUEPRINT.md) - システム設計の詳細
- [IMPLEMENTATION_PLAN.md](./IMPLEMENTATION_PLAN.md) - 実装計画
- [CLAUDE.md](../CLAUDE.md) - 開発ガイドライン

---

## チェックリスト

### 初回セットアップ完了確認

- [ ] ローカルで `uv sync` が成功
- [ ] GCP プロジェクトが作成され、課金が有効
- [ ] `terraform apply`（第1段階）が正常完了
- [ ] コンテナイメージのビルド・プッシュが成功
- [ ] `terraform apply`（第2段階）が正常完了
- [ ] Cloud SQL にスキーマが適用済み
- [ ] Google Drive フォルダがサービスアカウントに共有済み
- [ ] `.env` ファイルが生成済み
- [ ] ローカルで API と UI が起動
- [ ] API ヘルスチェックが成功
- [ ] Ingester ジョブが正常実行

### 本番運用開始前

- [ ] `db_tier` を本番向けに変更（例: `db-custom-2-7680`）
- [ ] Cloud Run の `min_instances` を検討
- [ ] GitHub Actions シークレットを設定
- [ ] アラートポリシーを設定（任意）
- [ ] バックアップ設定を確認（任意）
