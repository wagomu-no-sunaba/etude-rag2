# Terraform 入門ガイド - etude-rag2 プロジェクト

このドキュメントは、Terraform初心者がetude-rag2プロジェクトのTerraformコードを理解するために必要な知識をまとめたものです。

---

## 目次

1. [Terraformとは](#1-terraformとは)
2. [HCL (HashiCorp Configuration Language) の基本文法](#2-hcl-hashicorp-configuration-language-の基本文法)
3. [本プロジェクトで使用しているリソース一覧](#3-本プロジェクトで使用しているリソース一覧)
4. [ファイル構成と役割](#4-ファイル構成と役割)
5. [公式ドキュメントリンク集](#5-公式ドキュメントリンク集)

---

## 1. Terraformとは

Terraformは、**Infrastructure as Code (IaC)** ツールです。インフラストラクチャ（サーバー、データベース、ネットワークなど）をコードとして宣言的に定義し、自動的にプロビジョニング（構築）できます。

### 主な特徴

- **宣言的**: 「望ましい状態」を記述すると、Terraformが現在の状態からその状態に変更してくれる
- **プロバイダー**: AWS、GCP、Azureなど多くのクラウドに対応
- **状態管理**: `terraform.tfstate` ファイルで現在のインフラ状態を追跡

### 基本的なワークフロー

```bash
terraform init      # 初期化（プロバイダーのダウンロード）
terraform plan      # 変更内容のプレビュー
terraform apply     # 変更の適用
terraform destroy   # リソースの削除
```

### 公式ドキュメント

- [Terraform 公式チュートリアル](https://developer.hashicorp.com/terraform/tutorials)
- [GCP 向けチュートリアル](https://developer.hashicorp.com/terraform/tutorials/gcp-get-started)

---

## 2. HCL (HashiCorp Configuration Language) の基本文法

TerraformはHCLという独自の設定言語を使用します。

### 2.1 基本構文

```hcl
# コメント（#または//で始まる）

/* 複数行
   コメント */

# ブロックの基本構造
ブロックタイプ "ラベル1" "ラベル2" {
  引数名 = 値
}
```

### 2.2 ブロックの種類

#### `terraform` ブロック - バージョンと設定

```hcl
terraform {
  required_version = ">= 1.5.0"    # Terraformのバージョン制約

  required_providers {
    google = {
      source  = "hashicorp/google"  # プロバイダーのソース
      version = "~> 5.0"            # プロバイダーのバージョン
    }
  }
}
```

**本プロジェクトの例**: `versions.tf`

#### `provider` ブロック - クラウドプロバイダーの設定

```hcl
provider "google" {
  project = var.project_id    # var.XXX は変数の参照
  region  = var.region
}
```

プロバイダーは、どのクラウドサービス（GCP、AWSなど）を使うかを定義します。

#### `variable` ブロック - 入力変数の定義

```hcl
variable "project_id" {
  description = "GCP project ID"    # 説明
  type        = string              # 型（string, number, bool, list, map など）
}

variable "region" {
  description = "GCP region"
  type        = string
  default     = "us-central1"       # デフォルト値
}
```

**本プロジェクトの例**: `variables.tf`

#### `resource` ブロック - インフラリソースの定義

```hcl
resource "google_compute_network" "vpc" {
  name                    = "my-vpc"
  auto_create_subnetworks = false
}
```

- 第1ラベル: リソースタイプ（例: `google_compute_network`）
- 第2ラベル: ローカル名（コード内で参照する名前）

#### `output` ブロック - 出力値の定義

```hcl
output "api_service_url" {
  description = "API の URL"
  value       = google_cloud_run_v2_service.api.uri
}
```

`terraform apply` 後に値を表示したり、他のモジュールから参照できます。

#### `locals` ブロック - ローカル変数

```hcl
locals {
  api_image_base = "${var.region}-docker.pkg.dev/${var.project_id}/repo/api"
}
```

繰り返し使う値を変数化できます。

### 2.3 メタ引数

リソースブロック内で使用できる特別な引数です。

#### `for_each` - 複数リソースの作成

```hcl
resource "google_project_service" "services" {
  for_each = toset([
    "run.googleapis.com",
    "sqladmin.googleapis.com",
  ])

  service = each.value    # each.value で現在の要素にアクセス
}
```

**本プロジェクトの例**: `main.tf` のAPI有効化

#### `depends_on` - 明示的な依存関係

```hcl
resource "google_service_account" "cloud_run" {
  account_id = "my-sa"

  depends_on = [google_project_service.services]  # この先に作成を待つ
}
```

Terraformは通常自動で依存関係を推測しますが、明示的に指定が必要な場合があります。

#### `lifecycle` - リソースのライフサイクル制御

```hcl
resource "google_cloud_run_v2_service" "api" {
  # ...

  lifecycle {
    ignore_changes = [
      template[0].containers[0].image,  # この属性の変更を無視
    ]
  }
}
```

**本プロジェクトの例**: Cloud RunのイメージはCI/CDで更新されるため、Terraformでは変更を無視

#### `count` - 条件付きリソース作成

```hcl
resource "google_cloud_run_v2_service_iam_member" "api_public" {
  count = var.environment == "dev" ? 1 : 0  # dev環境でのみ作成

  # ...
}
```

**本プロジェクトの例**: dev環境でのみパブリックアクセスを許可

### 2.4 文字列補間と参照

```hcl
# 変数の参照
name = var.project_id

# リソースの属性参照
value = google_sql_database_instance.postgres.private_ip_address

# 文字列補間
name = "etude-rag2-${var.environment}"    # 例: "etude-rag2-dev"
```

### 公式ドキュメント

- [HCL 構文ドキュメント](https://developer.hashicorp.com/terraform/language/syntax/configuration)
- [構文概要](https://developer.hashicorp.com/terraform/language/syntax)
- [for_each メタ引数](https://developer.hashicorp.com/terraform/language/meta-arguments/for_each)
- [depends_on メタ引数](https://developer.hashicorp.com/terraform/language/meta-arguments/depends_on)
- [lifecycle メタ引数](https://developer.hashicorp.com/terraform/language/meta-arguments/lifecycle)

---

## 3. 本プロジェクトで使用しているリソース一覧

### 3.1 Google Cloud Provider リソース

| リソースタイプ | 用途 | ドキュメント |
|--------------|------|-------------|
| `google_project_service` | GCP API の有効化 | [Registry](https://registry.terraform.io/providers/hashicorp/google/latest/docs/resources/google_project_service) |
| `google_service_account` | サービスアカウント作成 | [Registry](https://registry.terraform.io/providers/hashicorp/google/latest/docs/resources/google_service_account) |
| `google_project_iam_member` | IAM 権限の付与 | [Registry](https://registry.terraform.io/providers/hashicorp/google/latest/docs/resources/google_project_iam) |
| `google_compute_network` | VPC ネットワーク | [Registry](https://registry.terraform.io/providers/hashicorp/google/latest/docs/resources/compute_network) |
| `google_compute_subnetwork` | サブネット | [Registry](https://registry.terraform.io/providers/hashicorp/google/latest/docs/resources/compute_subnetwork) |
| `google_vpc_access_connector` | VPC コネクタ（サーバーレス接続用） | [Registry](https://registry.terraform.io/providers/hashicorp/google/latest/docs/resources/vpc_access_connector) |
| `google_compute_global_address` | グローバル IP アドレス | [Registry](https://registry.terraform.io/providers/hashicorp/google/latest/docs/resources/compute_global_address) |
| `google_service_networking_connection` | プライベートサービス接続 | [Registry](https://registry.terraform.io/providers/hashicorp/google/latest/docs/resources/service_networking_connection) |
| `google_sql_database_instance` | Cloud SQL インスタンス | [Registry](https://registry.terraform.io/providers/hashicorp/google/latest/docs/resources/sql_database_instance) |
| `google_sql_database` | データベース | [Registry](https://registry.terraform.io/providers/hashicorp/google/latest/docs/resources/sql_database) |
| `google_sql_user` | データベースユーザー | [Registry](https://registry.terraform.io/providers/hashicorp/google/latest/docs/resources/sql_user) |
| `google_cloud_run_v2_service` | Cloud Run サービス | [Registry](https://registry.terraform.io/providers/hashicorp/google/latest/docs/resources/cloud_run_v2_service) |
| `google_cloud_run_v2_job` | Cloud Run ジョブ | [Registry](https://registry.terraform.io/providers/hashicorp/google/latest/docs/resources/cloud_run_v2_job) |
| `google_cloud_run_v2_service_iam_member` | Cloud Run IAM | [Registry](https://registry.terraform.io/providers/hashicorp/google/latest/docs/resources/cloud_run_v2_service_iam) |
| `google_secret_manager_secret` | シークレット定義 | [Registry](https://registry.terraform.io/providers/hashicorp/google/latest/docs/resources/secret_manager_secret) |
| `google_secret_manager_secret_version` | シークレット値 | [Registry](https://registry.terraform.io/providers/hashicorp/google/latest/docs/resources/secret_manager_secret_version) |
| `google_secret_manager_secret_iam_member` | シークレット IAM | [Registry](https://registry.terraform.io/providers/hashicorp/google/latest/docs/resources/secret_manager_secret_iam) |
| `google_artifact_registry_repository` | コンテナレジストリ | [Registry](https://registry.terraform.io/providers/hashicorp/google/latest/docs/resources/artifact_registry_repository) |
| `google_iam_workload_identity_pool` | Workload Identity Pool | [Registry](https://registry.terraform.io/providers/hashicorp/google/latest/docs/resources/iam_workload_identity_pool) |
| `google_iam_workload_identity_pool_provider` | Workload Identity Provider | [Registry](https://registry.terraform.io/providers/hashicorp/google/latest/docs/resources/iam_workload_identity_pool_provider) |
| `google_service_account_iam_member` | サービスアカウント IAM | [Registry](https://registry.terraform.io/providers/hashicorp/google/latest/docs/resources/google_service_account_iam) |

### 3.2 Random Provider リソース

| リソースタイプ | 用途 | ドキュメント |
|--------------|------|-------------|
| `random_password` | ランダムパスワード生成 | [Registry](https://registry.terraform.io/providers/hashicorp/random/latest/docs/resources/password) |

---

## 4. ファイル構成と役割

```
terraform/
├── versions.tf          # Terraform/プロバイダーのバージョン設定
├── variables.tf         # 入力変数の定義
├── main.tf              # 主要リソース（API有効化、サービスアカウント、VPC）
├── cloudsql.tf          # Cloud SQL (PostgreSQL) 関連
├── cloudrun.tf          # Cloud Run サービス/ジョブ
├── secrets.tf           # Secret Manager 関連
├── artifact_registry.tf # Artifact Registry (Docker リポジトリ)
├── iam.tf               # IAM と Workload Identity Federation
└── outputs.tf           # 出力値の定義
```

### 各ファイルの詳細

#### `versions.tf`
```hcl
terraform {
  required_version = ">= 1.5.0"
  required_providers {
    google      = { source = "hashicorp/google", version = "~> 5.0" }
    google-beta = { source = "hashicorp/google-beta", version = "~> 5.0" }
  }
}
```
- Terraformのバージョン要件
- 使用するプロバイダー（google, google-beta）の定義

#### `variables.tf`
入力変数の定義。主なカテゴリ：
- **基本設定**: `project_id`, `region`, `environment`
- **Cloud SQL**: `db_tier`, `db_name`, `db_user`
- **Cloud Run**: `cloud_run_cpu`, `cloud_run_memory`, スケーリング設定
- **AI/ML**: `embedding_model`, `llm_model`, `reranker_model`
- **検索**: `hybrid_search_k`, `rrf_k`

#### `main.tf`
インフラの基盤：
- **GCP API の有効化** (`google_project_service`)
- **サービスアカウント** (`google_service_account`)
- **IAM ロール割り当て** (`google_project_iam_member`)
- **VPC ネットワーク** (`google_compute_network`, `google_compute_subnetwork`)
- **VPC コネクタ** (`google_vpc_access_connector`)
- **プライベート IP** (`google_compute_global_address`)

#### `cloudsql.tf`
Cloud SQL PostgreSQL：
- **インスタンス** (`google_sql_database_instance`) - PostgreSQL 16
- **データベース** (`google_sql_database`)
- **ユーザー** (`google_sql_user`)
- **パスワード** (`random_password` + Secret Manager)

#### `cloudrun.tf`
3つのCloud Runコンポーネント：
1. **API サーバー** (`google_cloud_run_v2_service.api`) - FastAPI
2. **Streamlit UI** (`google_cloud_run_v2_service.streamlit`)
3. **Ingester ジョブ** (`google_cloud_run_v2_job.ingester`) - データ取り込み

#### `secrets.tf`
機密情報の管理：
- `db_password` - データベースパスワード
- `drive_folder_id` - Google Drive フォルダ ID
- `my_email` - ACL フィルタ用メール
- `service_account_key` - サービスアカウントキー
- `app_config` - アプリケーション設定 (JSON)

#### `artifact_registry.tf`
Docker イメージの保存場所：
- コンテナレジストリの作成
- クリーンアップポリシー（最新10バージョンを保持）
- イメージ URI のローカル変数定義

#### `iam.tf`
認証とアクセス制御：
- **デプロイ用サービスアカウント** - GitHub Actions から使用
- **Workload Identity Federation** - GitHub Actions のキーレス認証
- 各種 IAM ロール割り当て

#### `outputs.tf`
作成されたリソースの情報出力：
- Cloud Run URL
- Cloud SQL 接続情報
- サービスアカウント情報
- GitHub Actions 設定値

---

## 5. 公式ドキュメントリンク集

### Terraform 基礎

| トピック | リンク |
|---------|--------|
| Terraform 入門チュートリアル | [HashiCorp Developer](https://developer.hashicorp.com/terraform/tutorials) |
| GCP 向けチュートリアル | [GCP Get Started](https://developer.hashicorp.com/terraform/tutorials/gcp-get-started) |
| HCL 構文リファレンス | [Syntax](https://developer.hashicorp.com/terraform/language/syntax/configuration) |
| 構文概要 | [Syntax Overview](https://developer.hashicorp.com/terraform/language/syntax) |

### Google Cloud Provider

| トピック | リンク |
|---------|--------|
| Google Provider 概要 | [Terraform Registry](https://registry.terraform.io/providers/hashicorp/google/latest/docs) |
| Google Cloud + Terraform 概要 | [Google Cloud Docs](https://cloud.google.com/docs/terraform/terraform-overview) |
| Getting Started ガイド | [Getting Started](https://registry.terraform.io/providers/hashicorp/google/latest/docs/guides/getting_started) |

### 本プロジェクトで使用する主要リソース

| リソース | ドキュメント |
|---------|-------------|
| Cloud Run v2 Service | [Registry](https://registry.terraform.io/providers/hashicorp/google/latest/docs/resources/cloud_run_v2_service) |
| Cloud Run v2 Job | [Registry](https://registry.terraform.io/providers/hashicorp/google/latest/docs/resources/cloud_run_v2_job) |
| Cloud SQL Instance | [Registry](https://registry.terraform.io/providers/hashicorp/google/latest/docs/resources/sql_database_instance) |
| Secret Manager Secret | [Registry](https://registry.terraform.io/providers/hashicorp/google/latest/docs/resources/secret_manager_secret) |
| VPC Network | [Registry](https://registry.terraform.io/providers/hashicorp/google/latest/docs/resources/compute_network) |
| Artifact Registry | [Registry](https://registry.terraform.io/providers/hashicorp/google/latest/docs/resources/artifact_registry_repository) |
| Workload Identity Pool | [Registry](https://registry.terraform.io/providers/hashicorp/google/latest/docs/resources/iam_workload_identity_pool) |
| Random Password | [Registry](https://registry.terraform.io/providers/hashicorp/random/latest/docs/resources/password) |

### メタ引数

| トピック | リンク |
|---------|--------|
| for_each | [for_each](https://developer.hashicorp.com/terraform/language/meta-arguments/for_each) |
| depends_on | [depends_on](https://developer.hashicorp.com/terraform/language/meta-arguments/depends_on) |
| lifecycle | [lifecycle](https://developer.hashicorp.com/terraform/language/meta-arguments/lifecycle) |
| count | [count](https://developer.hashicorp.com/terraform/language/meta-arguments/count) |

---

## 付録: 本プロジェクトのアーキテクチャ図

```
                          ┌─────────────────────────────────────────────┐
                          │              Google Cloud Platform          │
                          │                                             │
┌──────────────┐          │  ┌─────────────────────────────────────┐   │
│   GitHub     │ Workload │  │            Cloud Run                 │   │
│   Actions    │─Identity─│  │  ┌─────────┐  ┌───────────┐         │   │
│              │  (OIDC)  │  │  │   API   │  │ Streamlit │         │   │
└──────────────┘          │  │  │ Server  │  │    UI     │         │   │
                          │  │  └────┬────┘  └─────┬─────┘         │   │
                          │  │       │             │                │   │
                          │  │  ┌────┴─────────────┴────┐          │   │
                          │  │  │    VPC Connector      │          │   │
                          │  │  └────────────┬──────────┘          │   │
                          │  └───────────────┼─────────────────────┘   │
                          │                  │                          │
                          │  ┌───────────────┼─────────────────────┐   │
                          │  │            VPC │Network              │   │
                          │  │  ┌────────────┴──────────┐          │   │
                          │  │  │      Cloud SQL        │          │   │
                          │  │  │    (PostgreSQL +      │          │   │
                          │  │  │     pgvector)         │          │   │
                          │  │  └───────────────────────┘          │   │
                          │  └─────────────────────────────────────┘   │
                          │                                             │
                          │  ┌─────────────┐  ┌─────────────────────┐  │
                          │  │   Secret    │  │  Artifact Registry  │  │
                          │  │   Manager   │  │  (Docker Images)    │  │
                          │  └─────────────┘  └─────────────────────┘  │
                          │                                             │
                          │  ┌─────────────┐  ┌─────────────────────┐  │
                          │  │  Vertex AI  │  │   Google Drive      │  │
                          │  │ (Embedding) │  │   (Source Docs)     │  │
                          │  └─────────────┘  └─────────────────────┘  │
                          └─────────────────────────────────────────────┘
```

---

## 次のステップ

1. [GCP 向け Terraform チュートリアル](https://developer.hashicorp.com/terraform/tutorials/gcp-get-started) を完了する
2. 本プロジェクトの `terraform/` ディレクトリで `terraform init` を実行してみる
3. `terraform plan` で変更内容をプレビューする
4. 各リソースのドキュメントを読み、引数の意味を理解する
