from qcloud_cos import CosConfig, CosS3Client
import sys

# COS credentials from create_media response
secret_id = "AKIDHIhy_7aTPFToQG2LIWxFSwm6Z6zhRJh80Y9-S3ELModB7tTUCI1f6tnmtQaOs7YF"
secret_key = "AqArduuaGpwPy2mR3dhvmmg0+sfD+IVhExk8Qh1FyOM="
token = "3k8x7ZWvtEiG2T25vOlQt7vKQ6uHqKPaef29b2ff86cf596d722c98446fd9c2c61oEGNiKt0tsaadNXlrFMOD0mp1SFgsl1qkRJSkTb7jT5Qt3DTi6HkB_ZCfQwSylDxuzYJwoVDCbUXKhBKzeAOjalMt74HZhaURIFP-YvnTR6G3FSrivZvvBXUZx3B8Z1H_iYnBrczwoXhYMYPq7Z1cqtbuO2FHXxOv5Kz5jdgkOlL3-DyfFCktOaLmavNWDD_zHLPXvXxWpJFXfH-6yJf-w3bMyLOi8A4yXO3arVF_kAPkWaKQ-7sAAbxv0o-KIZGYzf1IAchevHvns87rUuRxpbPzVk0YtvuDl5xZAUTv9CLT65CUj9YVhemfH9KQSWoc7VUzuJxw3RJRKSKXiPXmiWaJbyKWginB0yP5dB3upPK_nSr4E96nHWjw-ojvELgw5MydBjw-0q-ckcMaj7Is1yV6AFmCiBWFFj0oQB8cZ65CAtlFaiK_33N1AAkV_n-xo2fq6kCd_LefMSv0lrtp35H4TV1VeSC4icGXW4P0F3u4xcvfIQVbRSyxhmLcvWY2RkqseIjfFYXtSyO4fFmt6SnGesL1FsyntIt_wuBvR7NrzhTpB-vljig1tRzyoCXofLKYFnPdsWV7p9gbcmTCAjvCiajFrjMXG7E-0JPbjnbDCr8tKGPueJJmnMw8EtRjotaQJYkeYbUrTiZBueblD7rQeDwYpD0G8kMnrt8slUYriwv-gOp92U2lYYSIU5SLjTFVzGJZvoGAfF766alcO6JFeaowhA6MEGxVNoTXHs5GitTcI_ctZm6cABg-1sG0KPsLCGsRPzuxh274Lz7EsD41ka3u_-IqYkXWU7shkdl0QUGuH95yWjKJrZwKe-"
region = "ap-shanghai"
bucket = "ima-media-prod-1258344701"
cos_key = "2/I2kYEe4oeHwMPqer5fRfj9A/file_manager/019feae4d179779c935cd533d2fad77f.pdf"
file_path = r"C:\Users\Administrator\Desktop\新建文件夹\GBZ117-2022_工业探伤放射防护标准.pdf"

# Create COS config with temporary credentials
config = CosConfig(
    Region=region,
    SecretId=secret_id,
    SecretKey=secret_key,
    Token=token,
    Scheme="https"
)

client = CosS3Client(config)

print(f"Uploading file: {file_path}")
print(f"Bucket: {bucket}")
print(f"Key: {cos_key}")

# Upload file using put_object
with open(file_path, "rb") as f:
    file_data = f.read()

print(f"File size: {len(file_data)} bytes")

try:
    response = client.put_object(
        Bucket=bucket,
        Body=file_data,
        Key=cos_key,
        ContentType="application/pdf"
    )
    print(f"ETag: {response['ETag']}")
    print("SUCCESS: File uploaded to COS!")
except Exception as e:
    print(f"FAILED: {e}")
    sys.exit(1)
