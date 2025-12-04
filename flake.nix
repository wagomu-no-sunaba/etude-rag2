{
  description = "Python development environment with uv";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    flake-utils.url = "github:numtide/flake-utils";
  };

  outputs = { self, nixpkgs, flake-utils }:
    flake-utils.lib.eachDefaultSystem (system:
      let
        pkgs = import nixpkgs {
          inherit system;
          config = {
            allowUnfreePredicate = pkg: builtins.elem (nixpkgs.lib.getName pkg) [
              "terraform"
            ];
          };
        };
      in
      {
        devShells.default = pkgs.mkShell {
          buildInputs = with pkgs; [
            # Python
            python312

            # uv - Python package installer
            uv

            # PostgreSQL client libraries (psycopg2の依存関係)
            postgresql

            # zlib (FlagEmbeddingの依存関係zlib-stateに必要)
            zlib

            # ビルドツール
            gcc
            stdenv.cc.cc.lib

            # その他の開発ツール
            git

            # Infrastructure as Code
            terraform

            # Google Cloud SQL Proxy
            google-cloud-sql-proxy
          ];

          shellHook = ''
            echo "🐍 Python + uv development environment"
            echo "Python version: $(python --version)"
            echo "uv version: $(uv --version)"
            echo "Terraform version: $(terraform --version | head -n1)"
            echo "Cloud SQL Proxy version: $(cloud-sql-proxy --version 2>&1 | head -n1)"
            echo ""
            echo "Usage:"
            echo "  uv sync          # Install dependencies"
            echo "  uv run python    # Run Python with dependencies"
            echo "  uv add <package> # Add a new dependency"
            echo "  terraform init   # Initialize Terraform"
            echo "  terraform plan   # Preview changes"
            echo "  terraform apply  # Apply changes"
          '';

          # ライブラリのパスを設定
          LD_LIBRARY_PATH = "${pkgs.postgresql.lib}/lib:${pkgs.zlib}/lib:${pkgs.stdenv.cc.cc.lib}/lib";

          # コンパイル時のヘッダファイルパスを設定
          CFLAGS = "-I${pkgs.zlib.dev}/include";
          LDFLAGS = "-L${pkgs.zlib}/lib";
        };
      }
    );
}
