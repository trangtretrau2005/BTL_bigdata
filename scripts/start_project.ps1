$ErrorActionPreference = 'Stop'
Set-Location (Split-Path $PSScriptRoot -Parent)
if (-not (Test-Path '.env')) { Copy-Item '.env.example' '.env' }
docker compose up -d --build
if ($LASTEXITCODE -ne 0) { throw 'Docker Compose failed' }
docker compose exec -T ollama ollama pull bge-m3
if ($LASTEXITCODE -ne 0) { throw 'Embedding model download failed' }
docker compose exec -T ollama ollama pull qwen3:4b-instruct-2507-q4_K_M
if ($LASTEXITCODE -ne 0) { throw 'Chat model download failed' }
docker compose exec -T app python -m scripts.setup_voice
if ($LASTEXITCODE -ne 0) { Write-Warning 'Local voice download failed; online speech remains available. Retry: docker compose exec -T app python -m scripts.setup_voice' }
Write-Host 'UI: http://localhost:8501'
Write-Host 'HDFS: http://localhost:9870 | Qdrant: http://localhost:6333/dashboard'
Write-Host 'Data: docker compose exec -T app python -m scripts.run_pipeline --step all --rebuild'
