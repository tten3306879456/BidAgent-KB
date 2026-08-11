#!/usr/bin/env python3
"""Upload files to Tencent Cloud COS using temporary credentials from ima-mcp."""
import hashlib
import hmac
import json
import sys
import urllib.request
import urllib.error

def calc_cos_signature(secret_id, secret_key, method, path, headers, key_time):
    """Calculate COS v5 signature."""
    # SignKey = HMAC-SHA1(SecretKey, KeyTime) -> hex
    sign_key = hmac.new(secret_key.encode(), key_time.encode(), hashlib.sha1).hexdigest()

    # HeaderList = sorted header keys joined by ";"
    header_keys = sorted(headers.keys())
    header_list = ";".join(header_keys)

    # UrlParamList = empty for PUT
    url_param_list = ""

    # FormatString
    header_str = "&".join(f"{k}={headers[k]}" for k in header_keys)
    format_string = f"{method.lower()}\n/{path}\n{url_param_list}\n{header_str}\n"

    # StringToSign
    format_string_hash = hashlib.sha1(format_string.encode()).hexdigest()
    string_to_sign = f"sha1\n{key_time}\n{format_string_hash}\n"

    # Signature
    signature = hmac.new(sign_key.encode(), string_to_sign.encode(), hashlib.sha1).hexdigest()

    # Authorization header
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
    """Upload a file to COS using temporary credentials."""
    secret_id = cos_credential["secret_id"]
    secret_key = cos_credential["secret_key"]
    token = cos_credential["token"]
    bucket = cos_credential["bucket_name"]
    region = cos_credential["region"]
    cos_key = cos_credential["cos_key"]
    start_time = cos_credential["start_time"]
    expired_time = cos_credential["expired_time"]

    key_time = f"{start_time};{expired_time}"

    # Build COS URL
    host = f"{bucket}.cos.{region}.myqcloud.com"
    url = f"https://{host}/{cos_key}"

    # Read file content
    with open(file_path, "rb") as f:
        file_data = f.read()

    # Headers for signature (only host is needed)
    sign_headers = {"host": host}

    # Calculate signature
    # cos_key path: extract just the key part for signature path
    # The path in FormatString should be the cos_key without leading slash
    sign_path = cos_key

    auth = calc_cos_signature(
        secret_id, secret_key, "put", sign_path, sign_headers, key_time
    )

    # Build request headers
    headers = {
        "Authorization": auth,
        "x-cos-security-token": token,
        "Content-Type": content_type,
        "Content-Length": str(len(file_data)),
        "Host": host,
    }

    # Create and send request
    req = urllib.request.Request(url, data=file_data, headers=headers, method="PUT")

    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            status = response.status
            body = response.read().decode()
            print(f"  Upload successful! Status: {status}")
            return True
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        print(f"  Upload FAILED! HTTP {e.code}")
        print(f"  Response: {body[:500]}")
        return False
    except Exception as e:
        print(f"  Upload FAILED! Error: {e}")
        return False


def main():
    files = [
        {
            "path": r"C:\Users\Administrator\WorkBuddy\2026-08-07-16-36-41\知识库种子内容\废标条款模式库_种子版.md",
            "media_id": "markdown_5ed40ba2d36a302455d0d1e3065167fa_05fdda443a5b0a5e9437cce8db665fc8001a9d12b7c0755c",
            "cos_credential": {
                "token": "ME7nLdFUrvrOb47R32X6jkZimCRwZYCab797d56ca1feccf371739c38de23f704b8af6nPYjxtXc6Y-8NEkC3n84K1cNumGFq3-er-lf3lXP64bU-_aEgtbS2p2XDQrRSTWbNCjLWTUpejfz-rEFYi-TpSc5l2EVOr7eZRMZCwNV84JQFZzbFGAt8t-Sx6Cv94gyjgcKiqlomI_BV4wb7n6A6sQ5TEHoiP7ETgyGVPmzqzPLyGMEnt2qFljenSr1_dk-68apnwzmtNasDVhfWjA77ZlfCMkHDQHGYCuoDVw5a-ZuXZn0IYvZsdpgqEi471r8gkcDftXH4Cn2XKu-vzI-TOOq2hAsBNnauNDR1PAB95xSOBsDPOALOgh3zkTsQrBdEQwFIXtnMQRYsBr3mi_TZ-52T3yHYHIx6A7cdouUdIKzFz6r5NpdhlqDHaz-arm-ymg-0oal7dhcHHPkiXs8KIePg1UjiWhqRL22VfAXxeHU8ogwJweZPwxSWJ-_GLQC-CqG_H-6ip2V7dpA2X8zEnIUs-y8QJg5ujBmz3tqnt_mU2IM2F5FhBw8vpXKQJcgmO71NOYINZF2nuJtusZPVUhVPfe5eMyFrhF9VY3JUljk2sr17nMUMDhpJKhMZYwLlp41g08QMId6UxG3l8TACBaa9gCkaNB612MY1OTnaSanOyHnYY4IZf8oWUNBg-umfT3aFZGWfHDFRqhnJTRi0vL1a7LfiqeyNwT6u3tMpAh8JSBkTbjjDt83BQHCH-dMc1l-EdAi35Gw9270Z6HDlO8nt5JDqo-79T4lR1RIKzrNSPCls4tXNfJv33wsYSx_Zh98yrtPU4Uo_KeWaffahpYNL-SJ3WGiVQoV_0nLAB0UjwejVt7q-FmiWmc",
                "secret_id": "AKIDjEiSih0WtpW5Jpp5XxnFVUIEgIP2YNjBALb5U8mw-ZpzHmFI01evJc07EPPqZl8d",
                "secret_key": "un0Uh39oJbucr5yGb2p7Dr6MoQMszN0lvsOsqOunfI0=",
                "start_time": "1786333612",
                "expired_time": "1786376812",
                "appid": "1258344701",
                "bucket_name": "ima-media-prod-1258344701",
                "region": "ap-shanghai",
                "custom_domain": "ima-media-prod.image.myqcloud.com",
                "cos_key": "2/I2kYEe4oeHwMPqer5fRfj9A/file_manager/019fe9c7cb73712b9ab22b5aaf12880d.md"
            },
            "content_type": "text/markdown"
        },
        {
            "path": r"C:\Users\Administrator\WorkBuddy\2026-08-07-16-36-41\知识库种子内容\标书核心法规汇编_v1.0.md",
            "media_id": "markdown_5ed40ba2d36a302455d0d1e3065167fa_63538948e10d8eb81da91099925701b3001a9d12b7c0755c",
            "cos_credential": {
                "token": "ME7nLdFUrvrOb47R32X6jkZimCRwZYCa212dae50b7ef673004f1db322e3f25d5b8af6nPYjxtXc6Y-8NEkC_yfFKvggYISbDi8R7mp2KAgWMOeHmi5B86ojiIU2qShffKODrdjo9aRbMPBEBAgF0LG298gurJzlUoxzOU0oGpPN_NCuuGyTQBhIalOg39Zu8qTtuFzCFaWzWhuNNYE351oGiJ4umOb6qYbTvVgmt2HQ-ElqmEFJeDBml_880BevCRs1prHZfQDnswr9jSw9EUIdPKKEGibtuusKsgoR15xc9YlVzEmlM-TWtK2D-imxxIp3d5TDVusV5mbZwuzIo8uf9ddL45PnlapFuu_gBHOM_2dv58217cbRBkUNY67Egbt66oyW9uZG-YV7ITPz71gXURAlkqUNiM2dXXg68aDkDwzmUXuiWxgIVtCH2K-55CZwVX2pY6v4SP-nEqACZOncaS5hMsSvK_jWtf6-f9gSO6aJGRjnX75hYwus8IOcFrsoD9Oq2X_eOtuwC40KrBCZSDIGy7oG7JLCnuHZ-p3r_FHH8qsEYbqiQ8K0ivZve-N6Ip9h0wsZZ92F_7nhklbQogazcnHVYPteQ0VpswPXn29kAQ0lTzxzO6fjyc3GRtEy8xQz_xev8hyhM0lY9zkCYjnFS0iEXUlr3vl1_hDGXiYLWhp0zEU1jIj1oK8is1CElCa1y0iSIDDWlhLf72VXOC_2ozdb8BRUk0BM8GooKG9C_-utcH4F1UVYgz0nKZc7hUJWuEseawo6sXGzZpi8dX-RZMSybYgc3xBo4xWkfJyoK7LAxr42VBRBWn_CK5lYHfSocCamO3q4Ur8mec2d09y0bytHlbkLz9CygMRy50YUaMgy9QlSG4fOuGS",
                "secret_id": "AKID4-vFHbV-1GLyjDDMB-V8Cwt905ELtBoEgfiO0GLyP_rvd7owhtDyDXqOdjDskadR",
                "secret_key": "T2dX83P9Bw8Uu5Ap05sJ9SX8ouIEYZr6qVjhEnVN8Ww=",
                "start_time": "1786333617",
                "expired_time": "1786376817",
                "appid": "1258344701",
                "bucket_name": "ima-media-prod-1258344701",
                "region": "ap-shanghai",
                "custom_domain": "ima-media-prod.image.myqcloud.com",
                "cos_key": "2/I2kYEe4oeHwMPqer5fRfj9A/file_manager/019fe9c7dd997dec980c03ce6cd95931.md"
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

    # Output media IDs for next step
    print("\n--- Media IDs for add_knowledge ---")
    for r in results:
        if r["success"]:
            print(f"{r['media_id']}")


if __name__ == "__main__":
    main()
