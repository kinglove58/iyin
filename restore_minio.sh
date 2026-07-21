#!/bin/sh
set -e
cd ~/iyin
S3_ACCESS_KEY=$(grep '^S3_ACCESS_KEY=' .env | cut -d= -f2-)
S3_SECRET_KEY=$(grep '^S3_SECRET_KEY=' .env | cut -d= -f2-)
S3_BUCKET=$(grep '^S3_BUCKET=' .env | cut -d= -f2-)
docker run --rm --network afs-external-net --entrypoint sh -v "$(pwd)/minio-backup:/backup" minio/mc:RELEASE.2025-08-13T08-35-41Z -c "mc alias set local http://minio:9000 \"$S3_ACCESS_KEY\" \"$S3_SECRET_KEY\" && mc mb --ignore-existing local/$S3_BUCKET && mc mirror --overwrite /backup local/$S3_BUCKET"
