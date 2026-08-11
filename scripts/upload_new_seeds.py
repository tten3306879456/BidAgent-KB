#!/usr/bin/env python3
"""Upload 3 new seed content files to COS using temporary credentials from ima-mcp."""
import hashlib
import hmac
import sys
import urllib.request
import urllib.error

def calc_cos_signature(secret_id, secret_key, method, path, headers, key_time):
    sign_key = hmac.new(secret_key.encode(), key_time.encode(), hashlib.sha1).hexdigest()
    header_keys = sorted(headers.keys())
    header_list = ";".join(header_keys)
    url_param_list = ""
    header_str = "&".join(f"{k}={headers[k]}" for k in header_keys)
    format_string = f"{method.lower()}\n/{path}\n{url_param_list}\n{header_str}\n"
    format_string_hash = hashlib.sha1(format_string.encode()).hexdigest()
    string_to_sign = f"sha1\n{key_time}\n{format_string_hash}\n"
    signature = hmac.new(sign_key.encode(), string_to_sign.encode(), hashlib.sha1).hexdigest()
    auth = (
        f"q-sign-algorithm=sha1"
        f"&q-ak={secret_id}"
        f"&q-sign-time={key_time}"
        f"&q-key-time={key_time}"
        f"&q-header-list={header_list}"
        f"&q-url-param-list={url_param_list}"
        f"&q-signature={signature}"
    )
    return auth

def upload_to_cos(file_path, cos_credential, content_type):
    secret_id = cos_credential["secret_id"]
    secret_key = cos_credential["secret_key"]
    token = cos_credential["token"]
    bucket = cos_credential["bucket_name"]
    region = cos_credential["region"]
    cos_key = cos_credential["cos_key"]
    start_time = cos_credential["start_time"]
    expired_time = cos_credential["expired_time"]

    key_time = f"{start_time};{expired_time}"
    host = f"{bucket}.cos.{region}.myqcloud.com"
    url = f"https://{host}/{cos_key}"

    with open(file_path, "rb") as f:
        file_data = f.read()

    sign_headers = {"host": host}
    sign_path = cos_key
    auth = calc_cos_signature(secret_id, secret_key, "put", sign_path, sign_headers, key_time)

    headers = {
        "Authorization": auth,
        "x-cos-security-token": token,
        "Content-Type": content_type,
        "Content-Length": str(len(file_data)),
        "Host": host,
    }

    req = urllib.request.Request(url, data=file_data, headers=headers, method="PUT")
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            print(f"  Upload successful! Status: {response.status}")
            return True
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        print(f"  Upload FAILED! HTTP {e.code}")
        print(f"  Response: {body[:500]}")
        return False
    except Exception as e:
        print(f"  Upload FAILED! Error: {e}")
        return False

files = [
    {
        "path": r"C:\Users\Administrator\WorkBuddy\2026-08-07-16-36-41\知识库种子内容\行业技术标准库_种子版.md",
        "media_id": "markdown_5ed40ba2d36a302455d0d1e3065167fa_81b302cdc3d07f63a5730a2dbcdfed34001a9d12b7c0755c",
        "cos_credential": {
            "token": "3k8x7ZWvtEiG2T25vOlQt7vKQ6uHqKPa62dc478e365150350b81a8768e43d8ce1oEGNiKt0tsaadNXlrFMOJ5MfQX9PEHsTYLRYH0mxmguv866Meb4o5XSL1IQuOoEHp7E2AWSQu9g8gVkqlKJo8pzAgp1SyYcXiW2Cb2BqA-NKt3L1U6B0O0YyJrTbEJ2VCUJjEZ7GCfcbDJxZZXjgMBbY1L5ccGRHpWb-eVIoE0QuASKaHHgja59TGqoFac-yG4ad3p8SGSENQGAmahv8R9UTb0Xw2Eku1QoGPw7UWweYk1Cy3kMAaj1zxcPOz3PUFaILQ_tVe9I7LmgzQ9SoeswyNqkzTJGuN7ND7eyGwXcNMIXH8wnp0qefmpSwq8-x0ISxpD5HFpbDzwWkmC6hwnyZtQNR22hLbc6_EeJU6VpO-dxclPMqkjxy263pPAgkPht_Kcr1db1hEw9onQlBYjfpyCyXNMB_GEyFX0uOQgGCV1uqsDYtsDXunDLIEjVFkF-DyHYkW7Ab9bn1ykRmyBovpqDjsPf3NPxzn3tB5oap0ufdG6CFAVQjzGR-85Wt0YxT7Moeb6ZVVMU9OQ1_BWsj4Pbemz4N-xltovRzNq9u7yvIi_mxDfEaKlsqnMaLrgFg6DgEoysYEf76HflmQC2rQdyNonMGBRFQGiCwnWYeR_8c4y8jnSCJmmOXSHFo-UqYx3DSz4GcZqT5mwRRo0xhs1Q0B3Nc6YtXHp22FJbWIPclDbiPcOtg9LcFQzkl4nN99cfacb2UuoUdUKlZ6SzhrokpQhQIHp0RwTS1k7O-_Zh37n5tpQbjlHHq64IpgppiwTOSyVjMcaj3E1kX-XKlaxjVai1tyLzYHwLEt7allSQuOGJNapbQu7qqcas",
            "secret_id": "AKIDott6RynZtmktDvPwzFHD6kxnuGvpW7aDae0H_QEn1jvx0O1i7qauOUwrt3nQyuww",
            "secret_key": "HS3tOo6d73ZA1jIvXYPoHAeadux2JNpdlDyr74mmDrI=",
            "start_time": "1786337999",
            "expired_time": "1786381199",
            "appid": "1258344701",
            "bucket_name": "ima-media-prod-1258344701",
            "region": "ap-shanghai",
            "custom_domain": "ima-media-prod.image.myqcloud.com",
            "cos_key": "2/I2kYEe4oeHwMPqer5fRfj9A/file_manager/019fea0abb5c78839c46197a928fb3cd.md"
        },
        "content_type": "text/markdown"
    },
    {
        "path": r"C:\Users\Administrator\WorkBuddy\2026-08-07-16-36-41\知识库种子内容\招投标报价与商务法规专题库_种子版.md",
        "media_id": "markdown_5ed40ba2d36a302455d0d1e3065167fa_1c3c4e2d81a8ce7f61ed5ba8a5b49d86001a9d12b7c0755c",
        "cos_credential": {
            "token": "01y4YTL1NNu1tUFJeUjUsSw0AMnRz1wa423cff6be6a235da2232d3e341b9d4feOAQGPnhHTbklKRC1YFaTEsyMcUzOE35TEVcXzpUUYQYB0VEgL7cnn-wqd-7rGWGeBKqovZ8k8bzCJLxDk_FL5fpYk-YhAUnIizxq_BT9KOkJ2iCiBRXxo0ekDztNDEYrJWgMFDisYZNg_lt3xihYHB6HNiUKunLamZyOu61l6WlMEUpNLNLnp8ruwI6V6aQebFwezXI_Xtf9zDr3WdyAL4NYmtOwjc3pALqrmlN5uCEvuwPS61YSdtgL6tSzWJMNLG2ohcEaHzL0LCh52TbOhlOqPFiouJH33igecn_CwlCNpMu-7Yuspg1naMfd6b8uRXkd-0v3emmgwqq9jNBs4xYgA1cdbdgIHQkgwK3d1hL-GxJPvlLImA-GAhwkQ-uyt1Zcdh10F2ua5UYQxp9qhktYDbt-12ruLskZbLmR6lWCubdFdPxSWKal7IEJE-2x1AR90MOqiaJsudFa2A_593DC_rhupaiztRSPnCjpguTQrmrk3Vu4QMUYSgAH_ybuulBGjeGpFTxMnil7zjYsbxR842ywlvRKB7x1Bnh_xTPrdbig221tg1v3-UjPUXlfjg6buCBnnBWNUjiVv-8HCi_v0iORIye4nkzLqgSs1_Roc3grmKNEipR5YwZIfsLr7vQjVa-onty28X_UUtGtAMR4T0rXXIMzkYgcSzTCglipQwE18VceWhOEfCqYXdontr07IP_Zm_kSCMxjbuhF24TjerSkJH4cDNtweNajOaISL9zSGHFZXT9HtrdzzU3m-pK3XP1HAp2kGwa6ZrXMZSVI_71EKBcQexvsH3qOg52yyDmZ7wOSMlCwMhXJ8uT0",
            "secret_id": "AKIDKYnpH7btSWEFO-BDTo46eNu8F_FgkGzaG-5hjDldLRi0O0MrDrkT-faq4-9DqRLj",
            "secret_key": "j3ULUwW2FjF5322BQOuBQqecYIWpkKy0gWRVR2EKeZg=",
            "start_time": "1786338003",
            "expired_time": "1786381203",
            "appid": "1258344701",
            "bucket_name": "ima-media-prod-1258344701",
            "region": "ap-shanghai",
            "custom_domain": "ima-media-prod.image.myqcloud.com",
            "cos_key": "2/I2kYEe4oeHwMPqer5fRfj9A/file_manager/019fea0ac8b17df39151eef3e6b138c6.md"
        },
        "content_type": "text/markdown"
    },
    {
        "path": r"C:\Users\Administrator\WorkBuddy\2026-08-07-16-36-41\知识库种子内容\资质等效替代规则库_种子版.md",
        "media_id": "markdown_5ed40ba2d36a302455d0d1e3065167fa_e7e204523c6406116c716ffdce14fbf9001a9d12b7c0755c",
        "cos_credential": {
            "token": "01y4YTL1NNu1tUFJeUjUsSw0AMnRz1wa4598261b9722b0c4574a80625fe35f5cOAQGPnhHTbklKRC1YFaTEiorLzEAKHCxNNqqBvJFA-EVUwPOwrBb_uL-YEvGWZsIGRAxyEtkUKbNdT6TgmxSdPUPkeiahhMBxhGhdCjoef5LYwQZX8lbdFWeiCmlldKUcRljrNWbPNBXXHohH8XG0z93GuW5zl34cxNmPx_zFVn0BUZNfN6kCWIyLiIhzGWRmc7Ufj0t0r8IaPuMxFDz1rSQeUTlElwFolxxWtwiFEnX1u_ucryBzzz9Qnb_KQoTo4TCRkp700B9FWX6GN1FmvqCvt_TgJ9E2ZdJjZE-24hZpup6NVeKXVomKsDgLOU9rCIKN-GssM_g-HH59GvdIUruR_tn1i4qLmptwUcK9wqB67PIQiUQgyCoad0l-VQ3FhXlBLQUKgnGAm08KvE-kaUWmu_O2I4vEZJ0vHeT6qclU5Iz4d7uOajvluTmcE2d4fd9foWlzDosjNxFJ8AGmUrIHN2rD18-nXzL7jWO11c3lC7NhVp_oOifd12kOTrEu-mQuR0xnhSrhRzSyioJKa4WkPEJKs0alVOVeFm90I3fzcAx-1O8gaxbUY6KXtL7ZxAopSJZyIa-4c7mmwbrBIGc1vt0LZP8HGhiljPEX3qewSlyF0SqFvTv52Wu6ZufNxXKhWYfzP1rgEaouHhvujWkbJjaHqVhzjMIfP6sY0kGN5E7XbRkkn9xhj1m12NBVsDXu-zLNVKT-2Wb2V_cU6a8L07BvV9KXJXJpjggqOQkWuzH2v9aPw-2m47Di4DOljUNipPEEqLPojbOm2lWi_a_5sbR2usELa7aeMCN4kH78NCRouGzsFrqgUVXFiJH",
            "secret_id": "AKIDOmQnTSaxYKbucNEDLgqwlda9nw_3gWPg3ANaDEvHbdPPuTCch-iUsmoUC91T2a-a",
            "secret_key": "Gj9PtPaDr3sMqAQ5jUcrH4Pnrsbn7vOD+yatlf0+PCg=",
            "start_time": "1786338006",
            "expired_time": "1786381206",
            "appid": "1258344701",
            "bucket_name": "ima-media-prod-1258344701",
            "region": "ap-shanghai",
            "custom_domain": "ima-media-prod.image.myqcloud.com",
            "cos_key": "2/I2kYEe4oeHwMPqer5fRfj9A/file_manager/019fea0ad67374a7b01830fc069dbe4e.md"
        },
        "content_type": "text/markdown"
    }
]

results = []
for i, f in enumerate(files):
    print(f"\n[{i+1}/{len(files)}] Uploading: {f['path'].split(chr(92))[-1]}")
    print(f"  media_id: {f['media_id']}")
    success = upload_to_cos(f["path"], f["cos_credential"], f["content_type"])
    results.append({"file": f["path"], "media_id": f["media_id"], "success": success})

print("\n--- Summary ---")
for r in results:
    status = "OK" if r["success"] else "FAILED"
    print(f"  {status}: {r['file'].split(chr(92))[-1]} -> media_id: {r['media_id']}")

print("\n--- Media IDs for add_knowledge ---")
for r in results:
    if r["success"]:
        print(r["media_id"])
