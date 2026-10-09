import os
import sys
import subprocess
import hashlib
import json
import shutil

ROOT = 'D:/PrivateAI'
SEVEN_ZIP = r'C:\Program Files\7-Zip\7z.exe'
ENCRYPTED_DIR = os.path.join(ROOT, 'encrypted_backup')
ARCHIVE_BASE = os.path.join(ENCRYPTED_DIR, 'infinity_ai_secure_data.7z')

def compute_sha256(filepath):
    h = hashlib.sha256()
    with open(filepath, 'rb') as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()

def create_encrypted_archive(passphrase):
    print("=== STEP 1: CREATING AES-256 ENCRYPTED ARCHIVE ===")
    if os.path.exists(ENCRYPTED_DIR):
        shutil.rmtree(ENCRYPTED_DIR)
    os.makedirs(ENCRYPTED_DIR, exist_ok=True)

    # We will pass specific directories relative to ROOT
    # to preserve their exact internal folder hierarchy
    targets = [
        'app/data',
        'app/chroma_db',
        'chroma_db',
        'data',
        'backups'
    ]

    # Add quarantined folders if any
    for d in os.listdir(os.path.join(ROOT, 'app')):
        if d.startswith('chroma_db_quarantined'):
            targets.append(f'app/{d}')

    # Filter only existing targets
    valid_targets = [t for t in targets if os.path.exists(os.path.join(ROOT, t))]

    cmd = [
        SEVEN_ZIP,
        'a',
        '-t7z',
        '-m0=lzma2',
        '-mx=9',
        '-mfb=64',
        '-md=32m',
        '-ms=on',
        '-mhe=on',            # Encrypt headers (filenames and metadata)
        f'-p{passphrase}',    # AES-256 key
        '-v80m',              # 80 MB volume chunks (< 90 MB GitHub limit)
        '-xr!.infinity-ai-authorized',
        '-xr!.device_auth.json',
        '-xr!.workspace_identity.json',
        '-xr!.quarantine_log.json',
        '-xr!*.key',
        '-xr!*.token',
        '-xr!__pycache__',
        '-xr!.pytest_cache',
        ARCHIVE_BASE
    ] + valid_targets

    print("Running 7-Zip compression and AES-256 encryption in", ROOT)
    res = subprocess.run(cmd, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if res.returncode != 0:
        print("ERROR in 7-Zip execution:")
        print(res.stderr)
        print(res.stdout)
        raise RuntimeError("7-Zip archive creation failed")

    print("Archive created successfully.")

    # List produced chunks
    chunks = sorted([f for f in os.listdir(ENCRYPTED_DIR) if f.startswith('infinity_ai_secure_data.7z')])
    print(f"Generated {len(chunks)} archive volume(s):")
    chunk_info = []
    for chk in chunks:
        chk_path = os.path.join(ENCRYPTED_DIR, chk)
        sz = os.path.getsize(chk_path)
        sha = compute_sha256(chk_path)
        print(f"  - {chk}: {sz} bytes ({sz / (1024*1024):.2f} MB) | SHA256: {sha}")
        chunk_info.append({
            "chunk_name": chk,
            "path": f"encrypted_backup/{chk}",
            "size_bytes": sz,
            "size_mb": round(sz / (1024*1024), 2),
            "sha256": sha
        })
    return chunk_info

def verify_archive(passphrase):
    print("\n=== STEP 2: VERIFYING ARCHIVE INTEGRITY ===")
    first_vol = os.path.join(ENCRYPTED_DIR, 'infinity_ai_secure_data.7z.001')
    if not os.path.exists(first_vol):
        first_vol = ARCHIVE_BASE
    cmd = [
        SEVEN_ZIP,
        't',
        f'-p{passphrase}',
        first_vol
    ]
    res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if res.returncode != 0:
        print("ERROR: Archive verification failed!")
        print(res.stderr)
        raise RuntimeError("Archive integrity test failed")
    print("Archive integrity verified: All files and chunks test OK.")

if __name__ == '__main__':
    passphrase = os.environ.get('INFINITY_BACKUP_PASSPHRASE', 'InfinityAI-OfflineSecureBackup-2026-VaultKey')
    chunks = create_encrypted_archive(passphrase)
    verify_archive(passphrase)
