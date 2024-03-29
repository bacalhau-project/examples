#!/usr/bin/env python
import os
import sys
import time


def main():
    # Get the current argument - the prefix string
    # If there is nothing, warn that we need a prefix
    if len(sys.argv) < 2:
        print("Usage: refresh-servers.py <prefix>")
        sys.exit(1)
    prefix = sys.argv[1]
    
    # Get the piped input from the previous command
    # If there is nothing, warn that we need input
    servers = sys.stdin.readlines()
    if len(servers) < 1:
        print("No servers received from previous command. Please run 'gcloud compute instances list -o json' and pipe the output to this command.")
        sys.exit(1)
    
    # Loop through the servers and refresh them - first print out a list of 'name'
    # Then print out the unique prefixes
    # SAMPLE_INPUT has been provided for you to test with
    for server in servers:
        
    
    
    
    
    
SAMPLE_INPUT = """
[
  {
    "canIpForward": false,
    "cpuPlatform": "Intel Broadwell",
    "creationTimestamp": "2024-03-01T20:54:37.955-08:00",
    "deletionProtection": false,
    "disks": [
      {
        "architecture": "X86_64",
        "autoDelete": true,
        "boot": true,
        "deviceName": "persistent-disk-0",
        "diskSizeGb": "10",
        "guestOsFeatures": [
          {
            "type": "VIRTIO_SCSI_MULTIQUEUE"
          },
          {
            "type": "SEV_CAPABLE"
          },
          {
            "type": "SEV_SNP_CAPABLE"
          },
          {
            "type": "SEV_LIVE_MIGRATABLE"
          },
          {
            "type": "SEV_LIVE_MIGRATABLE_V2"
          },
          {
            "type": "IDPF"
          },
          {
            "type": "UEFI_COMPATIBLE"
          },
          {
            "type": "GVNIC"
          }
        ],
        "index": 0,
        "interface": "SCSI",
        "kind": "compute#attachedDisk",
        "licenses": [
          "https://www.googleapis.com/compute/v1/projects/ubuntu-os-cloud/global/licenses/ubuntu-2004-lts"
        ],
        "mode": "READ_WRITE",
        "shieldedInstanceInitialState": {
          "dbxs": [
            {
              "content": "2gcDBhMRFQAAAAAAAAAAABENAAAAAvEOndKvSt9o7kmKqTR9N1ZlpzCCDPUCAQExDzANBglghkgBZQMEAgEFADALBgkqhkiG9w0BBwGgggsIMIIFGDCCBACgAwIBAgITMwAAABNryScg3e1ZiAAAAAAAEzANBgkqhkiG9w0BAQsFADCBgDELMAkGA1UEBhMCVVMxEzARBgNVBAgTCldhc2hpbmd0b24xEDAOBgNVBAcTB1JlZG1vbmQxHjAcBgNVBAoTFU1pY3Jvc29mdCBDb3Jwb3JhdGlvbjEqMCgGA1UEAxMhTWljcm9zb2Z0IENvcnBvcmF0aW9uIEtFSyBDQSAyMDExMB4XDTE2MDEwNjE4MzQxNVoXDTE3MDQwNjE4MzQxNVowgZUxCzAJBgNVBAYTAlVTMRMwEQYDVQQIEwpXYXNoaW5ndG9uMRAwDgYDVQQHEwdSZWRtb25kMR4wHAYDVQQKExVNaWNyb3NvZnQgQ29ycG9yYXRpb24xDTALBgNVBAsTBE1PUFIxMDAuBgNVBAMTJ01pY3Jvc29mdCBXaW5kb3dzIFVFRkkgS2V5IEV4Y2hhbmdlIEtleTCCASIwDQYJKoZIhvcNAQEBBQADggEPADCCAQoCggEBAKXiCkZgbboTnVZnS1h_JbnlcVst9wtFK8NQjTpeB9wirml3h-fzi8vzki0hSNBD2Dg49lGEvs4egyowmTsLu1TnBUH1f_Hi8Noa7fKXV6F93qYrTPajx5v9L7NedplWnMEPsRvJrQdrysTZwtoXMLYDhc8bQHI5nlJDfgqrB8JiC4A3vL9i19lkQOTq4PZb5AcVcE0wlG7lR_btoQN0g5B4_7pI2S_9mU1PXr1NBSEl48Kl4cJwO2GyvOVvxQ6wUSFTExmCBKrT3LnPU5lZY68n3MpZ5VY4skhrEt2dyf5bZNzkYTTouxC0n37OrMbGGq3tpv7JDD6E_Rfqua3dXYECAwEAAaOCAXIwggFuMBQGA1UdJQQNMAsGCSsGAQQBgjdPATAdBgNVHQ4EFgQUVsJIppTfox2XYoAJRIlnxAUOy2owUQYDVR0RBEowSKRGMEQxDTALBgNVBAsTBE1PUFIxMzAxBgNVBAUTKjMxNjMxKzJjNDU2Y2JjLTA1NDItNDdkOS05OWU1LWQzOWI4MTVjNTczZTAfBgNVHSMEGDAWgBRi_EPNoD6ky2cS0lvZVax7zLaKXzBTBgNVHR8ETDBKMEigRqBEhkJodHRwOi8vd3d3Lm1pY3Jvc29mdC5jb20vcGtpb3BzL2NybC9NaWNDb3JLRUtDQTIwMTFfMjAxMS0wNi0yNC5jcmwwYAYIKwYBBQUHAQEEVDBSMFAGCCsGAQUFBzAChkRodHRwOi8vd3d3Lm1pY3Jvc29mdC5jb20vcGtpb3BzL2NlcnRzL01pY0NvcktFS0NBMjAxMV8yMDExLTA2LTI0LmNydDAMBgNVHRMBAf8EAjAAMA0GCSqGSIb3DQEBCwUAA4IBAQCGjTFLjxsKmyLESJueg0S2Cp8N7MOq2IALsitZHwfYw2jMhY9b9kmKvIdSqVna1moZ6_zJSOS_JY6HkWZr6dDJe9Lj7xiW_e4qPP-KDrCVb02vBnK4EktVjTdJpyMhxBMdXUcq1eGl6518oCkQ27tu0-WZjaWEVsEY_gpQj0ye2UA4HYUYgJlpT24oJRi7TeQ03Nebb-ZrUkbf9uxl0OVV_mg2R5FDwOc3REoRAgv5jnw6X7ha5hlRCl2cLF27TFrFIRQQT4eSM33eDiitXXpYmD13jqKeHhLVXr07QSwqvKe1o1UYokJngP0pTwoDnt2qRuLnZ71jw732dSPN9B57MIIF6DCCA9CgAwIBAgIKYQrRiAAAAAAAAzANBgkqhkiG9w0BAQsFADCBkTELMAkGA1UEBhMCVVMxEzARBgNVBAgTCldhc2hpbmd0b24xEDAOBgNVBAcTB1JlZG1vbmQxHjAcBgNVBAoTFU1pY3Jvc29mdCBDb3Jwb3JhdGlvbjE7MDkGA1UEAxMyTWljcm9zb2Z0IENvcnBvcmF0aW9uIFRoaXJkIFBhcnR5IE1hcmtldHBsYWNlIFJvb3QwHhcNMTEwNjI0MjA0MTI5WhcNMjYwNjI0MjA1MTI5WjCBgDELMAkGA1UEBhMCVVMxEzARBgNVBAgTCldhc2hpbmd0b24xEDAOBgNVBAcTB1JlZG1vbmQxHjAcBgNVBAoTFU1pY3Jvc29mdCBDb3Jwb3JhdGlvbjEqMCgGA1UEAxMhTWljcm9zb2Z0IENvcnBvcmF0aW9uIEtFSyBDQSAyMDExMIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAxOi1ir-tVyawJsPq5_tXekQCXQcN2krldCrmsA_sbevsf7njWmMyfBEXTw7jC6c4FZOOxvXghLGamyzn9beR1gnh4sAEqKwwHN9I8wZQmmSnUX_IhU-PIIbO_i_hn_-CwO3pzc70U2piOgtDueIl_f4F-dTEFKsR4iOJjXC3pB1N7K7lnPoWwtfBy9ToxC_lme4kiwPsjfKL6sNK-0MREgt-tUeSbNzmBInr9TME6xABKnHl-YMTPP8lCS9odkb_uk--3K1xKliq-w7SeT3km2U7zCkqn_xyWaLrrpLv9jUTgMYC7ORfzJ12ze9jksGveUCEeYd_41Ko6J17B2mPFQIDAQABo4IBTzCCAUswEAYJKwYBBAGCNxUBBAMCAQAwHQYDVR0OBBYEFGL8Q82gPqTLZxLSW9lVrHvMtopfMBkGCSsGAQQBgjcUAgQMHgoAUwB1AGIAQwBBMAsGA1UdDwQEAwIBhjAPBgNVHRMBAf8EBTADAQH_MB8GA1UdIwQYMBaAFEVmUkPhflgRv9ZOniNVCDs6ImqoMFwGA1UdHwRVMFMwUaBPoE2GS2h0dHA6Ly9jcmwubWljcm9zb2Z0LmNvbS9wa2kvY3JsL3Byb2R1Y3RzL01pY0NvclRoaVBhck1hclJvb18yMDEwLTEwLTA1LmNybDBgBggrBgEFBQcBAQRUMFIwUAYIKwYBBQUHMAKGRGh0dHA6Ly93d3cubWljcm9zb2Z0LmNvbS9wa2kvY2VydHMvTWljQ29yVGhpUGFyTWFyUm9vXzIwMTAtMTAtMDUuY3J0MA0GCSqGSIb3DQEBCwUAA4ICAQDUhIj1FJQYAsoqPPsqkhwM16DR8ehSZqjuorV1epAAqi2kdlrqebe5N2pRexBk9uFk8gJnvveoG3i9us6IWGQM1lfIGaNfBdbbxtBpzkhLMrfrXdIw9cD1uLp4B6Mr_pvbNFaE7ILKrkElcJxr6f6QD9eWH-XnlB-yKgyNS_8oKRB799d8pdF2uQXIee0PkJKcwv7fb35sD3vUwUXdNFGWOQ_lXlbYGAWW9AemQrOgd_0IGfJxVsyfhiOkh8um_Vh-1GlnFZF-gfJ_E-UNi4o8h4Tr4869Q-WtLYSTjmorWnxE-lKqgcgtHLvgUt8AEfiaPcFgsOEztaOI0WUZChrnrHykwYKHTjixLw3FFIdv_Y0uvDm25-bD4OTNJ4TvlELvKYuQRkE7gRtn2PlDWWXLDbz9AJJP9HU7p6kk_FBBQHngLU8Kaid2blLtlml7rw_3hwXQRcKtUxSBH_swBKo3NmHaSmkbNNho7dYCz2yUDNPPbCJ5rbHwvAOiRmCpxAfCIYLx_fLoeTJgv9ispSIUS8rB2EvrfT9XNbLmT3W0sGADIlOukXkd1ptBHxWGVHCy3g01D3ywNHK6l2A78HnrorIcXaIWuIfF6Rv2tZclbzif45H6inmYw2kOt6McIAWX-MoUrgDXxPPAFBB1azSgG7WZYPNcsMVXTjbSMoS_njGCAcQwggHAAgEBMIGYMIGAMQswCQYDVQQGEwJVUzETMBEGA1UECBMKV2FzaGluZ3RvbjEQMA4GA1UEBxMHUmVkbW9uZDEeMBwGA1UEChMVTWljcm9zb2Z0IENvcnBvcmF0aW9uMSowKAYDVQQDEyFNaWNyb3NvZnQgQ29ycG9yYXRpb24gS0VLIENBIDIwMTECEzMAAAATa8knIN3tWYgAAAAAABMwDQYJYIZIAWUDBAIBBQAwDQYJKoZIhvcNAQEBBQAEggEAhabaxRIJ7nUZ-m__mIG0lII6yD-lxoeI8S83ZKTP8Qx5h5asySWl7420eGhna7zyaVRvVVIhkjOMIfcKr29LgzQpYDqPUc8aYAdGCsZKZGmHCMjEulnq5TDK79GKinzZfb2sAWXEJ68N8oNnY7faBKjHjmmJbAEz8ufE4DijgJ_NBov2xmhTZyNHQ7pB1iCdrEUGObzdJc0Qtmh3CNOEcmH0ukd8sTHE9acBBTFHS8dvreR_sP7dXClZJbJiWAFKvQn3EjCTiYizkZ4I_5xiqjHELht_ORQKN-Hnoqnl4kcRINhZRV7JlgAQDlBJLv3OTjShRO_ZWCdcu7PtwhweiSYWxMFMUJJArKlB-TaTQyiMDgAAAAAAADAAAAC9mvp3WQMyTb1gKPTnj3hLgLTZaTG_DQL9kaYeGdFPHaRS5m2yQIyoYE1BH5Jlnwq9mvp3WQMyTb1gKPTnj3hL9S-Do_qc-9aSD3IoJNvkA0U00luFByRrO5V9rG4bznq9mvp3WQMyTb1gKPTnj3hLxdnYoYbiyC0Jr6oqb38uc4cNPmT3LE4I72d5aoQPD729mvp3WQMyTb1gKPTnj3hLNjOE0U0fLgt4FWJkhMRZrVejGO9DliZgSNBYxaGbv3a9mvp3WQMyTb1gKPTnj3hLGuyEuEtsZaUSIKm-cYGWUjAhDWLW0zxImZxrKVorCga9mvp3WQMyTb1gKPTnj3hL5spo6UFGYprwP2nC-G5r72L5MLN8b7zIeLeN-YwDNOW9mvp3WQMyTb1gKPTnj3hLw6maRg2kZKBXw1htg8719K4ItxA5ee2JMnQt8O1TDGa9mvp3WQMyTb1gKPTnj3hLWPuUGu-VollDs_tfJRCg3z_kTFjJXgq4BIcpdWirl3G9mvp3WQMyTb1gKPTnj3hLU5HDovsRIQKmqh7cJa534Z9dbwnNCe6yUJkiv81Zkuq9mvp3WQMyTb1gKPTnj3hL1iYVfh1qcYvBJKuNony7ZQcsoDp7ayV9vcu9YPZe89G9mvp3WQMyTb1gKPTnj3hL0GPsKPZ-ulPxZC2_ff8zxqMq3YafYBP-Fi4sMvHL5W29mvp3WQMyTb1gKPTnj3hLKcbrUrQ8OqGLLNjtbqhgfO88-uG6_hFldVzy5hSESkS9mvp3WQMyTb1gKPTnj3hLkPvnDmnWM0CNPhcMaDLbstIJ4CclJ9-2PUnSlXKm9Ey9mvp3WQMyTb1gKPTnj3hLB17qBgWJVIugYLL-7RDaPCDH_psXzQJrlOimg7gRUji9mvp3WQMyTb1gKPTnj3hLB-bGqFhkb7HvxnkD_iixFgEfI2f-kua-KzaZnv850J69mvp3WQMyTb1gKPTnj3hLCd9fTlESCOx4uW0S0IEl_bYDho3jn29yknhSWZtlnCa9mvp3WQMyTb1gKPTnj3hLC7tDktqseribMKSsZXUxuXv6qwT5Cw2v5fm265CgY3S9mvp3WQMyTb1gKPTnj3hLDBiTOXYt8zarPdAGpGPfcVo5z7D0kkZcYA5sa9e9iYy9mvp3WQMyTb1gKPTnj3hLDQ2-ym8p7KBvMxp9cuSISxIJf7NImDoqFKDXP08QFA-9mvp3WQMyTb1gKPTnj3hLDcnz-5mWIUjDyoM2MnWNPtT8jQsAB7lbMeZSjyrNW_y9mvp3WQMyTb1gKPTnj3hLEG-s6s_s_U4wO3T0gKCAmOLQgCuTb47HdM4h8xaGaJy9mvp3WQMyTb1gKPTnj3hLF046C1tDxqYHu9NATwU0Hj3POWJnzpT4tQ4uI6nakgy9mvp3WQMyTb1gKPTnj3hLGDM0Kf8FYu2flwM-EUjc7uUtvi5JbVQQtc_WyGTS0Q-9mvp3WQMyTb1gKPTnj3hLK5nPJkIukv42X79Lww0nCGye4Ut6b_9E-y9rkAFpmTm9mvp3WQMyTb1gKPTnj3hLK78sp7jx2R8n7lK2-ypd0Em4WiubUpxdZmIGgQSwVfi9mvp3WQMyTb1gKPTnj3hLLHPZMyW6bcvlidSkxjxbk1VZ75L78FDtUMTiCFIG8X29mvp3WQMyTb1gKPTnj3hLLnCRZ4am93NRH6cYH6sPHXC1V8YyLqkjsqjTuStRr329mvp3WQMyTb1gKPTnj3hLMGYo-lR3MFcoukpGfefQOHpU9WnTdp_OXnXsidKNFZO9mvp3WQMyTb1gKPTnj3hLNgjtuvWtD0GkFKF3er8vr15nAzRnXsOZXmk1gp4MqtK9mvp3WQMyTb1gKPTnj3hLOEHSITaNFYPXXAoC5iFgOU1sTgpnYLb2B7kDYryFWwK9mvp3WQMyTb1gKPTnj3hLP86bn98-8J1UUrD5XuSBwrfwbXQ6c3lxVY5wE2rOPnO9mvp3WQMyTb1gKPTnj3hLQ5fayoOef2MHfLUMkt9DvC0vsqj1nyb8eg5L1Nl1FpK9mvp3WQMyTb1gKPTnj3hLR8wIYSfiBpqG4Dpr7yzUEPjFWm1r2zYhaMMbLOMqWt-9mvp3WQMyTb1gKPTnj3hLUYgx_nOCtRTQPhXGISKLirZUeb0Mv6PFwdD0jZwwYTW9mvp3WQMyTb1gKPTnj3hLWulJ6ohV65PkOdvGW9ouQoUsL99nifoUZzbjw0EPK1y9mvp3WQMyTb1gKPTnj3hLax0TgHjkQYqmjet7s14GYJLPR57rjOTNEufQcsy0L2a9mvp3WQMyTb1gKPTnj3hLbIhUR43VWeKTUbgmwGy4v-8rlK01ODWHctGT-C7RyhG9mvp3WQMyTb1gKPTnj3hLbxQo_3HJ2w7Vrx8ue7_Lq2R8wmXd9bKTzbYm9Qo6eF69mvp3WQMyTb1gKPTnj3hLcfKQb9IiSX5Uo0ZiqySX_MgQIHcP9RNo6ePZv8v9Y3W9mvp3WQMyTb1gKPTnj3hLcms-tlQEajDz-D2bls4D9nDpqAbRcIoDceYtxJ0sI8G9mvp3WQMyTb1gKPTnj3hLcuC9GGfPXZ1WqxWK3zvdvIK_MqjYqh2MXi9t8pQo1ti9mvp3WQMyTb1gKPTnj3hLeCevmTYs-vBxfa3ksb_gQ4rRccFa3cJIt1v4yqRLssW9mvp3WQMyTb1gKPTnj3hLgai5ZbuE04drlCmpVIHMlVMYz6oUEtgIyKM7_TP_8OS9mvp3WQMyTb1gKPTnj3hLgts7zrT2CEPOnZfD0YfNm1lBzT3oEA5YbyvaVjdXX2e9mvp3WQMyTb1gKPTnj3hLiVqXhfYXyh1-1E_BoUcLcfPxIjhi2f-dzDri35IWPa-9mvp3WQMyTb1gKPTnj3hLitZIWfGVtfWNr6qUC2phZ6zWeohuj0aTZBdyIcVZRbm9mvp3WQMyTb1gKPTnj3hLi_Q0tJ4AzPcVAqLNkAhlywHsOz2gPDW-UF_fe9Vj9SG9mvp3WQMyTb1gKPTnj3hLjY6iic_nChwHq3NlyyjuUe3TPPJQbeiI-63WDr-ASBy9mvp3WQMyTb1gKPTnj3hLmZjTY8SRvha9dLoQuU2SkQAWEXNv3KZDo2ZkvA8xWkK9mvp3WQMyTb1gKPTnj3hLnkppFzFhaC5V_ej-9WDriOwf_tyvBAAfZsDK9weytzS9mvp3WQMyTb1gKPTnj3hLprUVHzZV06KvDUcnWXlr5KQgDlSVp9hpdUxISIV0CKe9mvp3WQMyTb1gKPTnj3hLp_MvUI1OsP6tmgh--U7RugrsXeb372_wpiuTvt9dRY29mvp3WQMyTb1gKPTnj3hLrWgm4ZRtJtPq82hciNl9hd47Tcs9DuKugccFYNE8VyC9mvp3WQMyTb1gKPTnj3hLruuuMVEnEnPtlaouZxE57TGphWcwOjMimPg3CanVWqG9mvp3WQMyTb1gKPTnj3hLr-IDCvt9LNoT-fozOgLjT2dRr-wRsBDbzUQf30xAArO9mvp3WQMyTb1gKPTnj3hLtU8e5jZjH61oBY07CTcDGsG5DMsXBio5HMpor9vkDVW9mvp3WQMyTb1gKPTnj3hLuPB42YOiSsQzIWOTiDUUzZMsM68Y591wiEyCNfQnVza9mvp3WQMyTb1gKPTnj3hLuXoIiQWcA1_x1UtttTsRuXZmaNn5VSR8AosoN9egTNm9mvp3WQMyTb1gKPTnj3hLvIemaOgZZkictQjugFGDwZ5qzSTPF3mcoGLS44TaDqe9mvp3WQMyTb1gKPTnj3hLxAm9rEd1rdjbkqoitbcY-4yUoUYsH-mkFrldijOIwvy9mvp3WQMyTb1gKPTnj3hLxhfBqLHuKoEcKLWoG0yD18mLWwwnKB1hAgfr5pLCln-9mvp3WQMyTb1gKPTnj3hLyQ8zZhe45_mDl1QTyZfxC3PrJn_YoQy5472_xmer24u9mvp3WQMyTb1gKPTnj3hLy2uFi0DToJh2WBW1ksFRSklgT6_WCBnaiNenbpd4_ve9mvp3WQMyTb1gKPTnj3hLzjv6vlnWfOisjf1KFvfEPvnCJFE_vGVZV9c1-in1QM69mvp3WQMyTb1gKPTnj3hL2MvrlzX1Zys2fk-WzcdJaWFdFwdK6WxyTULOAhb48_q9mvp3WQMyTb1gKPTnj3hL6Swi6ztWQtZcHsLK8kfSWUc47rt_s4QaRJVvWeKw0fq9mvp3WQMyTb1gKPTnj3hL_d1uPSnqhMd0Pa1KG9vHALX-wbOR-TJAkIasxx3W29i9mvp3WQMyTb1gKPTnj3hL_mOoT3gsydP88sz5_BH70Ddgh4dY0mKF7RJmm9xubQG9mvp3WQMyTb1gKPTnj3hL_s-yMtEumUttSF0scWdyiqVSWYStXKYedRYiHweaFDa9mvp3WQMyTb1gKPTnj3hLyhcdYUqNfhIck5SM0P5V05mB-dEaqW4DRQpBUifCxlu9mvp3WQMyTb1gKPTnj3hLVbmbDeU9vP5IWqnHN88_thbvPZH6tZmqfKsZ7adjtbq9mvp3WQMyTb1gKPTnj3hLd90ZD6MNiP9eOwEaCuYeYgl4DBMLU17Lh-bwiIoLay-9mvp3WQMyTb1gKPTnj3hLyDyxOSKtmfVgdEZ13TfMlNytWh_Lpkcv7jQRcdk56IS9mvp3WQMyTb1gKPTnj3hLOwKHUz4Mw9DsGqgjy_CpQarYchV50cSZgC3Rw6Y2uKm9mvp3WQMyTb1gKPTnj3hLk5ru9PX6UeIzQMPy5JBIzohyUmr991LDp_Oj8ryfYEm9mvp3WQMyTb1gKPTnj3hLZFdb2RJ4mi4UrVb2NB9Sr2v4DPlEAHhZdenwTi1k10W9mvp3WQMyTb1gKPTnj3hLRcfIrnUKz7tI_DdSfWQS3WRNrtiRPM2KJMlNhWln344=",
              "fileType": "BIN"
            }
          ]
        },
        "source": "https://www.googleapis.com/compute/v1/projects/hydra-415522/zones/us-central1-a/disks/global-lb",
        "type": "PERSISTENT"
      },
      {
        "architecture": "X86_64",
        "autoDelete": false,
        "boot": false,
        "deviceName": "hydra-lb",
        "diskSizeGb": "10",
        "guestOsFeatures": [
          {
            "type": "VIRTIO_SCSI_MULTIQUEUE"
          },
          {
            "type": "SEV_CAPABLE"
          },
          {
            "type": "SEV_SNP_CAPABLE"
          },
          {
            "type": "SEV_LIVE_MIGRATABLE"
          },
          {
            "type": "SEV_LIVE_MIGRATABLE_V2"
          },
          {
            "type": "IDPF"
          },
          {
            "type": "UEFI_COMPATIBLE"
          },
          {
            "type": "GVNIC"
          }
        ],
        "index": 1,
        "interface": "SCSI",
        "kind": "compute#attachedDisk",
        "licenses": [
          "https://www.googleapis.com/compute/v1/projects/ubuntu-os-cloud/global/licenses/ubuntu-2004-lts"
        ],
        "mode": "READ_WRITE",
        "shieldedInstanceInitialState": {
          "dbxs": [
            {
              "content": "2gcDBhMRFQAAAAAAAAAAABENAAAAAvEOndKvSt9o7kmKqTR9N1ZlpzCCDPUCAQExDzANBglghkgBZQMEAgEFADALBgkqhkiG9w0BBwGgggsIMIIFGDCCBACgAwIBAgITMwAAABNryScg3e1ZiAAAAAAAEzANBgkqhkiG9w0BAQsFADCBgDELMAkGA1UEBhMCVVMxEzARBgNVBAgTCldhc2hpbmd0b24xEDAOBgNVBAcTB1JlZG1vbmQxHjAcBgNVBAoTFU1pY3Jvc29mdCBDb3Jwb3JhdGlvbjEqMCgGA1UEAxMhTWljcm9zb2Z0IENvcnBvcmF0aW9uIEtFSyBDQSAyMDExMB4XDTE2MDEwNjE4MzQxNVoXDTE3MDQwNjE4MzQxNVowgZUxCzAJBgNVBAYTAlVTMRMwEQYDVQQIEwpXYXNoaW5ndG9uMRAwDgYDVQQHEwdSZWRtb25kMR4wHAYDVQQKExVNaWNyb3NvZnQgQ29ycG9yYXRpb24xDTALBgNVBAsTBE1PUFIxMDAuBgNVBAMTJ01pY3Jvc29mdCBXaW5kb3dzIFVFRkkgS2V5IEV4Y2hhbmdlIEtleTCCASIwDQYJKoZIhvcNAQEBBQADggEPADCCAQoCggEBAKXiCkZgbboTnVZnS1h_JbnlcVst9wtFK8NQjTpeB9wirml3h-fzi8vzki0hSNBD2Dg49lGEvs4egyowmTsLu1TnBUH1f_Hi8Noa7fKXV6F93qYrTPajx5v9L7NedplWnMEPsRvJrQdrysTZwtoXMLYDhc8bQHI5nlJDfgqrB8JiC4A3vL9i19lkQOTq4PZb5AcVcE0wlG7lR_btoQN0g5B4_7pI2S_9mU1PXr1NBSEl48Kl4cJwO2GyvOVvxQ6wUSFTExmCBKrT3LnPU5lZY68n3MpZ5VY4skhrEt2dyf5bZNzkYTTouxC0n37OrMbGGq3tpv7JDD6E_Rfqua3dXYECAwEAAaOCAXIwggFuMBQGA1UdJQQNMAsGCSsGAQQBgjdPATAdBgNVHQ4EFgQUVsJIppTfox2XYoAJRIlnxAUOy2owUQYDVR0RBEowSKRGMEQxDTALBgNVBAsTBE1PUFIxMzAxBgNVBAUTKjMxNjMxKzJjNDU2Y2JjLTA1NDItNDdkOS05OWU1LWQzOWI4MTVjNTczZTAfBgNVHSMEGDAWgBRi_EPNoD6ky2cS0lvZVax7zLaKXzBTBgNVHR8ETDBKMEigRqBEhkJodHRwOi8vd3d3Lm1pY3Jvc29mdC5jb20vcGtpb3BzL2NybC9NaWNDb3JLRUtDQTIwMTFfMjAxMS0wNi0yNC5jcmwwYAYIKwYBBQUHAQEEVDBSMFAGCCsGAQUFBzAChkRodHRwOi8vd3d3Lm1pY3Jvc29mdC5jb20vcGtpb3BzL2NlcnRzL01pY0NvcktFS0NBMjAxMV8yMDExLTA2LTI0LmNydDAMBgNVHRMBAf8EAjAAMA0GCSqGSIb3DQEBCwUAA4IBAQCGjTFLjxsKmyLESJueg0S2Cp8N7MOq2IALsitZHwfYw2jMhY9b9kmKvIdSqVna1moZ6_zJSOS_JY6HkWZr6dDJe9Lj7xiW_e4qPP-KDrCVb02vBnK4EktVjTdJpyMhxBMdXUcq1eGl6518oCkQ27tu0-WZjaWEVsEY_gpQj0ye2UA4HYUYgJlpT24oJRi7TeQ03Nebb-ZrUkbf9uxl0OVV_mg2R5FDwOc3REoRAgv5jnw6X7ha5hlRCl2cLF27TFrFIRQQT4eSM33eDiitXXpYmD13jqKeHhLVXr07QSwqvKe1o1UYokJngP0pTwoDnt2qRuLnZ71jw732dSPN9B57MIIF6DCCA9CgAwIBAgIKYQrRiAAAAAAAAzANBgkqhkiG9w0BAQsFADCBkTELMAkGA1UEBhMCVVMxEzARBgNVBAgTCldhc2hpbmd0b24xEDAOBgNVBAcTB1JlZG1vbmQxHjAcBgNVBAoTFU1pY3Jvc29mdCBDb3Jwb3JhdGlvbjE7MDkGA1UEAxMyTWljcm9zb2Z0IENvcnBvcmF0aW9uIFRoaXJkIFBhcnR5IE1hcmtldHBsYWNlIFJvb3QwHhcNMTEwNjI0MjA0MTI5WhcNMjYwNjI0MjA1MTI5WjCBgDELMAkGA1UEBhMCVVMxEzARBgNVBAgTCldhc2hpbmd0b24xEDAOBgNVBAcTB1JlZG1vbmQxHjAcBgNVBAoTFU1pY3Jvc29mdCBDb3Jwb3JhdGlvbjEqMCgGA1UEAxMhTWljcm9zb2Z0IENvcnBvcmF0aW9uIEtFSyBDQSAyMDExMIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAxOi1ir-tVyawJsPq5_tXekQCXQcN2krldCrmsA_sbevsf7njWmMyfBEXTw7jC6c4FZOOxvXghLGamyzn9beR1gnh4sAEqKwwHN9I8wZQmmSnUX_IhU-PIIbO_i_hn_-CwO3pzc70U2piOgtDueIl_f4F-dTEFKsR4iOJjXC3pB1N7K7lnPoWwtfBy9ToxC_lme4kiwPsjfKL6sNK-0MREgt-tUeSbNzmBInr9TME6xABKnHl-YMTPP8lCS9odkb_uk--3K1xKliq-w7SeT3km2U7zCkqn_xyWaLrrpLv9jUTgMYC7ORfzJ12ze9jksGveUCEeYd_41Ko6J17B2mPFQIDAQABo4IBTzCCAUswEAYJKwYBBAGCNxUBBAMCAQAwHQYDVR0OBBYEFGL8Q82gPqTLZxLSW9lVrHvMtopfMBkGCSsGAQQBgjcUAgQMHgoAUwB1AGIAQwBBMAsGA1UdDwQEAwIBhjAPBgNVHRMBAf8EBTADAQH_MB8GA1UdIwQYMBaAFEVmUkPhflgRv9ZOniNVCDs6ImqoMFwGA1UdHwRVMFMwUaBPoE2GS2h0dHA6Ly9jcmwubWljcm9zb2Z0LmNvbS9wa2kvY3JsL3Byb2R1Y3RzL01pY0NvclRoaVBhck1hclJvb18yMDEwLTEwLTA1LmNybDBgBggrBgEFBQcBAQRUMFIwUAYIKwYBBQUHMAKGRGh0dHA6Ly93d3cubWljcm9zb2Z0LmNvbS9wa2kvY2VydHMvTWljQ29yVGhpUGFyTWFyUm9vXzIwMTAtMTAtMDUuY3J0MA0GCSqGSIb3DQEBCwUAA4ICAQDUhIj1FJQYAsoqPPsqkhwM16DR8ehSZqjuorV1epAAqi2kdlrqebe5N2pRexBk9uFk8gJnvveoG3i9us6IWGQM1lfIGaNfBdbbxtBpzkhLMrfrXdIw9cD1uLp4B6Mr_pvbNFaE7ILKrkElcJxr6f6QD9eWH-XnlB-yKgyNS_8oKRB799d8pdF2uQXIee0PkJKcwv7fb35sD3vUwUXdNFGWOQ_lXlbYGAWW9AemQrOgd_0IGfJxVsyfhiOkh8um_Vh-1GlnFZF-gfJ_E-UNi4o8h4Tr4869Q-WtLYSTjmorWnxE-lKqgcgtHLvgUt8AEfiaPcFgsOEztaOI0WUZChrnrHykwYKHTjixLw3FFIdv_Y0uvDm25-bD4OTNJ4TvlELvKYuQRkE7gRtn2PlDWWXLDbz9AJJP9HU7p6kk_FBBQHngLU8Kaid2blLtlml7rw_3hwXQRcKtUxSBH_swBKo3NmHaSmkbNNho7dYCz2yUDNPPbCJ5rbHwvAOiRmCpxAfCIYLx_fLoeTJgv9ispSIUS8rB2EvrfT9XNbLmT3W0sGADIlOukXkd1ptBHxWGVHCy3g01D3ywNHK6l2A78HnrorIcXaIWuIfF6Rv2tZclbzif45H6inmYw2kOt6McIAWX-MoUrgDXxPPAFBB1azSgG7WZYPNcsMVXTjbSMoS_njGCAcQwggHAAgEBMIGYMIGAMQswCQYDVQQGEwJVUzETMBEGA1UECBMKV2FzaGluZ3RvbjEQMA4GA1UEBxMHUmVkbW9uZDEeMBwGA1UEChMVTWljcm9zb2Z0IENvcnBvcmF0aW9uMSowKAYDVQQDEyFNaWNyb3NvZnQgQ29ycG9yYXRpb24gS0VLIENBIDIwMTECEzMAAAATa8knIN3tWYgAAAAAABMwDQYJYIZIAWUDBAIBBQAwDQYJKoZIhvcNAQEBBQAEggEAhabaxRIJ7nUZ-m__mIG0lII6yD-lxoeI8S83ZKTP8Qx5h5asySWl7420eGhna7zyaVRvVVIhkjOMIfcKr29LgzQpYDqPUc8aYAdGCsZKZGmHCMjEulnq5TDK79GKinzZfb2sAWXEJ68N8oNnY7faBKjHjmmJbAEz8ufE4DijgJ_NBov2xmhTZyNHQ7pB1iCdrEUGObzdJc0Qtmh3CNOEcmH0ukd8sTHE9acBBTFHS8dvreR_sP7dXClZJbJiWAFKvQn3EjCTiYizkZ4I_5xiqjHELht_ORQKN-Hnoqnl4kcRINhZRV7JlgAQDlBJLv3OTjShRO_ZWCdcu7PtwhweiSYWxMFMUJJArKlB-TaTQyiMDgAAAAAAADAAAAC9mvp3WQMyTb1gKPTnj3hLgLTZaTG_DQL9kaYeGdFPHaRS5m2yQIyoYE1BH5Jlnwq9mvp3WQMyTb1gKPTnj3hL9S-Do_qc-9aSD3IoJNvkA0U00luFByRrO5V9rG4bznq9mvp3WQMyTb1gKPTnj3hLxdnYoYbiyC0Jr6oqb38uc4cNPmT3LE4I72d5aoQPD729mvp3WQMyTb1gKPTnj3hLNjOE0U0fLgt4FWJkhMRZrVejGO9DliZgSNBYxaGbv3a9mvp3WQMyTb1gKPTnj3hLGuyEuEtsZaUSIKm-cYGWUjAhDWLW0zxImZxrKVorCga9mvp3WQMyTb1gKPTnj3hL5spo6UFGYprwP2nC-G5r72L5MLN8b7zIeLeN-YwDNOW9mvp3WQMyTb1gKPTnj3hLw6maRg2kZKBXw1htg8719K4ItxA5ee2JMnQt8O1TDGa9mvp3WQMyTb1gKPTnj3hLWPuUGu-VollDs_tfJRCg3z_kTFjJXgq4BIcpdWirl3G9mvp3WQMyTb1gKPTnj3hLU5HDovsRIQKmqh7cJa534Z9dbwnNCe6yUJkiv81Zkuq9mvp3WQMyTb1gKPTnj3hL1iYVfh1qcYvBJKuNony7ZQcsoDp7ayV9vcu9YPZe89G9mvp3WQMyTb1gKPTnj3hL0GPsKPZ-ulPxZC2_ff8zxqMq3YafYBP-Fi4sMvHL5W29mvp3WQMyTb1gKPTnj3hLKcbrUrQ8OqGLLNjtbqhgfO88-uG6_hFldVzy5hSESkS9mvp3WQMyTb1gKPTnj3hLkPvnDmnWM0CNPhcMaDLbstIJ4CclJ9-2PUnSlXKm9Ey9mvp3WQMyTb1gKPTnj3hLB17qBgWJVIugYLL-7RDaPCDH_psXzQJrlOimg7gRUji9mvp3WQMyTb1gKPTnj3hLB-bGqFhkb7HvxnkD_iixFgEfI2f-kua-KzaZnv850J69mvp3WQMyTb1gKPTnj3hLCd9fTlESCOx4uW0S0IEl_bYDho3jn29yknhSWZtlnCa9mvp3WQMyTb1gKPTnj3hLC7tDktqseribMKSsZXUxuXv6qwT5Cw2v5fm265CgY3S9mvp3WQMyTb1gKPTnj3hLDBiTOXYt8zarPdAGpGPfcVo5z7D0kkZcYA5sa9e9iYy9mvp3WQMyTb1gKPTnj3hLDQ2-ym8p7KBvMxp9cuSISxIJf7NImDoqFKDXP08QFA-9mvp3WQMyTb1gKPTnj3hLDcnz-5mWIUjDyoM2MnWNPtT8jQsAB7lbMeZSjyrNW_y9mvp3WQMyTb1gKPTnj3hLEG-s6s_s_U4wO3T0gKCAmOLQgCuTb47HdM4h8xaGaJy9mvp3WQMyTb1gKPTnj3hLF046C1tDxqYHu9NATwU0Hj3POWJnzpT4tQ4uI6nakgy9mvp3WQMyTb1gKPTnj3hLGDM0Kf8FYu2flwM-EUjc7uUtvi5JbVQQtc_WyGTS0Q-9mvp3WQMyTb1gKPTnj3hLK5nPJkIukv42X79Lww0nCGye4Ut6b_9E-y9rkAFpmTm9mvp3WQMyTb1gKPTnj3hLK78sp7jx2R8n7lK2-ypd0Em4WiubUpxdZmIGgQSwVfi9mvp3WQMyTb1gKPTnj3hLLHPZMyW6bcvlidSkxjxbk1VZ75L78FDtUMTiCFIG8X29mvp3WQMyTb1gKPTnj3hLLnCRZ4am93NRH6cYH6sPHXC1V8YyLqkjsqjTuStRr329mvp3WQMyTb1gKPTnj3hLMGYo-lR3MFcoukpGfefQOHpU9WnTdp_OXnXsidKNFZO9mvp3WQMyTb1gKPTnj3hLNgjtuvWtD0GkFKF3er8vr15nAzRnXsOZXmk1gp4MqtK9mvp3WQMyTb1gKPTnj3hLOEHSITaNFYPXXAoC5iFgOU1sTgpnYLb2B7kDYryFWwK9mvp3WQMyTb1gKPTnj3hLP86bn98-8J1UUrD5XuSBwrfwbXQ6c3lxVY5wE2rOPnO9mvp3WQMyTb1gKPTnj3hLQ5fayoOef2MHfLUMkt9DvC0vsqj1nyb8eg5L1Nl1FpK9mvp3WQMyTb1gKPTnj3hLR8wIYSfiBpqG4Dpr7yzUEPjFWm1r2zYhaMMbLOMqWt-9mvp3WQMyTb1gKPTnj3hLUYgx_nOCtRTQPhXGISKLirZUeb0Mv6PFwdD0jZwwYTW9mvp3WQMyTb1gKPTnj3hLWulJ6ohV65PkOdvGW9ouQoUsL99nifoUZzbjw0EPK1y9mvp3WQMyTb1gKPTnj3hLax0TgHjkQYqmjet7s14GYJLPR57rjOTNEufQcsy0L2a9mvp3WQMyTb1gKPTnj3hLbIhUR43VWeKTUbgmwGy4v-8rlK01ODWHctGT-C7RyhG9mvp3WQMyTb1gKPTnj3hLbxQo_3HJ2w7Vrx8ue7_Lq2R8wmXd9bKTzbYm9Qo6eF69mvp3WQMyTb1gKPTnj3hLcfKQb9IiSX5Uo0ZiqySX_MgQIHcP9RNo6ePZv8v9Y3W9mvp3WQMyTb1gKPTnj3hLcms-tlQEajDz-D2bls4D9nDpqAbRcIoDceYtxJ0sI8G9mvp3WQMyTb1gKPTnj3hLcuC9GGfPXZ1WqxWK3zvdvIK_MqjYqh2MXi9t8pQo1ti9mvp3WQMyTb1gKPTnj3hLeCevmTYs-vBxfa3ksb_gQ4rRccFa3cJIt1v4yqRLssW9mvp3WQMyTb1gKPTnj3hLgai5ZbuE04drlCmpVIHMlVMYz6oUEtgIyKM7_TP_8OS9mvp3WQMyTb1gKPTnj3hLgts7zrT2CEPOnZfD0YfNm1lBzT3oEA5YbyvaVjdXX2e9mvp3WQMyTb1gKPTnj3hLiVqXhfYXyh1-1E_BoUcLcfPxIjhi2f-dzDri35IWPa-9mvp3WQMyTb1gKPTnj3hLitZIWfGVtfWNr6qUC2phZ6zWeohuj0aTZBdyIcVZRbm9mvp3WQMyTb1gKPTnj3hLi_Q0tJ4AzPcVAqLNkAhlywHsOz2gPDW-UF_fe9Vj9SG9mvp3WQMyTb1gKPTnj3hLjY6iic_nChwHq3NlyyjuUe3TPPJQbeiI-63WDr-ASBy9mvp3WQMyTb1gKPTnj3hLmZjTY8SRvha9dLoQuU2SkQAWEXNv3KZDo2ZkvA8xWkK9mvp3WQMyTb1gKPTnj3hLnkppFzFhaC5V_ej-9WDriOwf_tyvBAAfZsDK9weytzS9mvp3WQMyTb1gKPTnj3hLprUVHzZV06KvDUcnWXlr5KQgDlSVp9hpdUxISIV0CKe9mvp3WQMyTb1gKPTnj3hLp_MvUI1OsP6tmgh--U7RugrsXeb372_wpiuTvt9dRY29mvp3WQMyTb1gKPTnj3hLrWgm4ZRtJtPq82hciNl9hd47Tcs9DuKugccFYNE8VyC9mvp3WQMyTb1gKPTnj3hLruuuMVEnEnPtlaouZxE57TGphWcwOjMimPg3CanVWqG9mvp3WQMyTb1gKPTnj3hLr-IDCvt9LNoT-fozOgLjT2dRr-wRsBDbzUQf30xAArO9mvp3WQMyTb1gKPTnj3hLtU8e5jZjH61oBY07CTcDGsG5DMsXBio5HMpor9vkDVW9mvp3WQMyTb1gKPTnj3hLuPB42YOiSsQzIWOTiDUUzZMsM68Y591wiEyCNfQnVza9mvp3WQMyTb1gKPTnj3hLuXoIiQWcA1_x1UtttTsRuXZmaNn5VSR8AosoN9egTNm9mvp3WQMyTb1gKPTnj3hLvIemaOgZZkictQjugFGDwZ5qzSTPF3mcoGLS44TaDqe9mvp3WQMyTb1gKPTnj3hLxAm9rEd1rdjbkqoitbcY-4yUoUYsH-mkFrldijOIwvy9mvp3WQMyTb1gKPTnj3hLxhfBqLHuKoEcKLWoG0yD18mLWwwnKB1hAgfr5pLCln-9mvp3WQMyTb1gKPTnj3hLyQ8zZhe45_mDl1QTyZfxC3PrJn_YoQy5472_xmer24u9mvp3WQMyTb1gKPTnj3hLy2uFi0DToJh2WBW1ksFRSklgT6_WCBnaiNenbpd4_ve9mvp3WQMyTb1gKPTnj3hLzjv6vlnWfOisjf1KFvfEPvnCJFE_vGVZV9c1-in1QM69mvp3WQMyTb1gKPTnj3hL2MvrlzX1Zys2fk-WzcdJaWFdFwdK6WxyTULOAhb48_q9mvp3WQMyTb1gKPTnj3hL6Swi6ztWQtZcHsLK8kfSWUc47rt_s4QaRJVvWeKw0fq9mvp3WQMyTb1gKPTnj3hL_d1uPSnqhMd0Pa1KG9vHALX-wbOR-TJAkIasxx3W29i9mvp3WQMyTb1gKPTnj3hL_mOoT3gsydP88sz5_BH70Ddgh4dY0mKF7RJmm9xubQG9mvp3WQMyTb1gKPTnj3hL_s-yMtEumUttSF0scWdyiqVSWYStXKYedRYiHweaFDa9mvp3WQMyTb1gKPTnj3hLyhcdYUqNfhIck5SM0P5V05mB-dEaqW4DRQpBUifCxlu9mvp3WQMyTb1gKPTnj3hLVbmbDeU9vP5IWqnHN88_thbvPZH6tZmqfKsZ7adjtbq9mvp3WQMyTb1gKPTnj3hLd90ZD6MNiP9eOwEaCuYeYgl4DBMLU17Lh-bwiIoLay-9mvp3WQMyTb1gKPTnj3hLyDyxOSKtmfVgdEZ13TfMlNytWh_Lpkcv7jQRcdk56IS9mvp3WQMyTb1gKPTnj3hLOwKHUz4Mw9DsGqgjy_CpQarYchV50cSZgC3Rw6Y2uKm9mvp3WQMyTb1gKPTnj3hLk5ru9PX6UeIzQMPy5JBIzohyUmr991LDp_Oj8ryfYEm9mvp3WQMyTb1gKPTnj3hLZFdb2RJ4mi4UrVb2NB9Sr2v4DPlEAHhZdenwTi1k10W9mvp3WQMyTb1gKPTnj3hLRcfIrnUKz7tI_DdSfWQS3WRNrtiRPM2KJMlNhWln344=",
              "fileType": "BIN"
            }
          ]
        },
        "source": "https://www.googleapis.com/compute/v1/projects/hydra-415522/zones/us-central1-a/disks/hydra-lb",
        "type": "PERSISTENT"
      }
    ],
    "fingerprint": "exN0PNgdXq8=",
    "id": "2976546273530679266",
    "kind": "compute#instance",
    "labelFingerprint": "42WmSpB8rSM=",
    "lastStartTimestamp": "2024-03-01T20:54:44.953-08:00",
    "machineType": "https://www.googleapis.com/compute/v1/projects/hydra-415522/zones/us-central1-a/machineTypes/e2-medium",
    "metadata": {
      "fingerprint": "kQD5BbHG6cw=",
      "items": [
        {
          "key": "device-name",
          "value": "hydra-lb"
        },
        {
          "key": "mount-hydra-lb",
          "value": "/olddisk"
        }
      ],
      "kind": "compute#metadata"
    },
    "name": "global-lb",
    "networkInterfaces": [
      {
        "accessConfigs": [
          {
            "kind": "compute#accessConfig",
            "name": "external-nat",
            "natIP": "34.71.149.24",
            "networkTier": "PREMIUM",
            "type": "ONE_TO_ONE_NAT"
          }
        ],
        "fingerprint": "G7KQmku8iTE=",
        "kind": "compute#networkInterface",
        "name": "nic0",
        "network": "https://www.googleapis.com/compute/v1/projects/hydra-415522/global/networks/global-network",
        "networkIP": "10.128.0.2",
        "stackType": "IPV4_ONLY",
        "subnetwork": "https://www.googleapis.com/compute/v1/projects/hydra-415522/regions/us-central1/subnetworks/global-network"
      }
    ],
    "scheduling": {
      "automaticRestart": true,
      "onHostMaintenance": "MIGRATE",
      "preemptible": false,
      "provisioningModel": "STANDARD"
    },
    "selfLink": "https://www.googleapis.com/compute/v1/projects/hydra-415522/zones/us-central1-a/instances/global-lb",
    "serviceAccounts": [
      {
        "email": "88991504323-compute@developer.gserviceaccount.com",
        "scopes": [
          "https://www.googleapis.com/auth/devstorage.read_only",
          "https://www.googleapis.com/auth/logging.write",
          "https://www.googleapis.com/auth/monitoring.write",
          "https://www.googleapis.com/auth/pubsub",
          "https://www.googleapis.com/auth/service.management.readonly",
          "https://www.googleapis.com/auth/servicecontrol",
          "https://www.googleapis.com/auth/trace.append"
        ]
      }
    ],
    "shieldedInstanceConfig": {
      "enableIntegrityMonitoring": true,
      "enableSecureBoot": false,
      "enableVtpm": true
    },
    "shieldedInstanceIntegrityPolicy": {
      "updateAutoLearnPolicy": true
    },
    "startRestricted": false,
    "status": "RUNNING",
    "tags": {
      "fingerprint": "yE93N1On7-o=",
      "items": [
        "default-allow-internal",
        "global-lb"
      ]
    },
    "zone": "https://www.googleapis.com/compute/v1/projects/hydra-415522/zones/us-central1-a"
  },
  {
    "canIpForward": false,
    "cpuPlatform": "AMD Rome",
    "creationTimestamp": "2024-03-05T11:26:59.530-08:00",
    "deletionProtection": false,
    "disks": [
      {
        "architecture": "X86_64",
        "autoDelete": true,
        "boot": true,
        "deviceName": "persistent-disk-0",
        "diskSizeGb": "10",
        "guestOsFeatures": [
          {
            "type": "VIRTIO_SCSI_MULTIQUEUE"
          },
          {
            "type": "SEV_CAPABLE"
          },
          {
            "type": "SEV_SNP_CAPABLE"
          },
          {
            "type": "SEV_LIVE_MIGRATABLE"
          },
          {
            "type": "SEV_LIVE_MIGRATABLE_V2"
          },
          {
            "type": "IDPF"
          },
          {
            "type": "UEFI_COMPATIBLE"
          },
          {
            "type": "GVNIC"
          }
        ],
        "index": 0,
        "interface": "SCSI",
        "kind": "compute#attachedDisk",
        "licenses": [
          "https://www.googleapis.com/compute/v1/projects/ubuntu-os-cloud/global/licenses/ubuntu-2204-lts"
        ],
        "mode": "READ_WRITE",
        "shieldedInstanceInitialState": {
          "dbxs": [
            {
              "content": "2gcDBhMRFQAAAAAAAAAAABENAAAAAvEOndKvSt9o7kmKqTR9N1ZlpzCCDPUCAQExDzANBglghkgBZQMEAgEFADALBgkqhkiG9w0BBwGgggsIMIIFGDCCBACgAwIBAgITMwAAABNryScg3e1ZiAAAAAAAEzANBgkqhkiG9w0BAQsFADCBgDELMAkGA1UEBhMCVVMxEzARBgNVBAgTCldhc2hpbmd0b24xEDAOBgNVBAcTB1JlZG1vbmQxHjAcBgNVBAoTFU1pY3Jvc29mdCBDb3Jwb3JhdGlvbjEqMCgGA1UEAxMhTWljcm9zb2Z0IENvcnBvcmF0aW9uIEtFSyBDQSAyMDExMB4XDTE2MDEwNjE4MzQxNVoXDTE3MDQwNjE4MzQxNVowgZUxCzAJBgNVBAYTAlVTMRMwEQYDVQQIEwpXYXNoaW5ndG9uMRAwDgYDVQQHEwdSZWRtb25kMR4wHAYDVQQKExVNaWNyb3NvZnQgQ29ycG9yYXRpb24xDTALBgNVBAsTBE1PUFIxMDAuBgNVBAMTJ01pY3Jvc29mdCBXaW5kb3dzIFVFRkkgS2V5IEV4Y2hhbmdlIEtleTCCASIwDQYJKoZIhvcNAQEBBQADggEPADCCAQoCggEBAKXiCkZgbboTnVZnS1h_JbnlcVst9wtFK8NQjTpeB9wirml3h-fzi8vzki0hSNBD2Dg49lGEvs4egyowmTsLu1TnBUH1f_Hi8Noa7fKXV6F93qYrTPajx5v9L7NedplWnMEPsRvJrQdrysTZwtoXMLYDhc8bQHI5nlJDfgqrB8JiC4A3vL9i19lkQOTq4PZb5AcVcE0wlG7lR_btoQN0g5B4_7pI2S_9mU1PXr1NBSEl48Kl4cJwO2GyvOVvxQ6wUSFTExmCBKrT3LnPU5lZY68n3MpZ5VY4skhrEt2dyf5bZNzkYTTouxC0n37OrMbGGq3tpv7JDD6E_Rfqua3dXYECAwEAAaOCAXIwggFuMBQGA1UdJQQNMAsGCSsGAQQBgjdPATAdBgNVHQ4EFgQUVsJIppTfox2XYoAJRIlnxAUOy2owUQYDVR0RBEowSKRGMEQxDTALBgNVBAsTBE1PUFIxMzAxBgNVBAUTKjMxNjMxKzJjNDU2Y2JjLTA1NDItNDdkOS05OWU1LWQzOWI4MTVjNTczZTAfBgNVHSMEGDAWgBRi_EPNoD6ky2cS0lvZVax7zLaKXzBTBgNVHR8ETDBKMEigRqBEhkJodHRwOi8vd3d3Lm1pY3Jvc29mdC5jb20vcGtpb3BzL2NybC9NaWNDb3JLRUtDQTIwMTFfMjAxMS0wNi0yNC5jcmwwYAYIKwYBBQUHAQEEVDBSMFAGCCsGAQUFBzAChkRodHRwOi8vd3d3Lm1pY3Jvc29mdC5jb20vcGtpb3BzL2NlcnRzL01pY0NvcktFS0NBMjAxMV8yMDExLTA2LTI0LmNydDAMBgNVHRMBAf8EAjAAMA0GCSqGSIb3DQEBCwUAA4IBAQCGjTFLjxsKmyLESJueg0S2Cp8N7MOq2IALsitZHwfYw2jMhY9b9kmKvIdSqVna1moZ6_zJSOS_JY6HkWZr6dDJe9Lj7xiW_e4qPP-KDrCVb02vBnK4EktVjTdJpyMhxBMdXUcq1eGl6518oCkQ27tu0-WZjaWEVsEY_gpQj0ye2UA4HYUYgJlpT24oJRi7TeQ03Nebb-ZrUkbf9uxl0OVV_mg2R5FDwOc3REoRAgv5jnw6X7ha5hlRCl2cLF27TFrFIRQQT4eSM33eDiitXXpYmD13jqKeHhLVXr07QSwqvKe1o1UYokJngP0pTwoDnt2qRuLnZ71jw732dSPN9B57MIIF6DCCA9CgAwIBAgIKYQrRiAAAAAAAAzANBgkqhkiG9w0BAQsFADCBkTELMAkGA1UEBhMCVVMxEzARBgNVBAgTCldhc2hpbmd0b24xEDAOBgNVBAcTB1JlZG1vbmQxHjAcBgNVBAoTFU1pY3Jvc29mdCBDb3Jwb3JhdGlvbjE7MDkGA1UEAxMyTWljcm9zb2Z0IENvcnBvcmF0aW9uIFRoaXJkIFBhcnR5IE1hcmtldHBsYWNlIFJvb3QwHhcNMTEwNjI0MjA0MTI5WhcNMjYwNjI0MjA1MTI5WjCBgDELMAkGA1UEBhMCVVMxEzARBgNVBAgTCldhc2hpbmd0b24xEDAOBgNVBAcTB1JlZG1vbmQxHjAcBgNVBAoTFU1pY3Jvc29mdCBDb3Jwb3JhdGlvbjEqMCgGA1UEAxMhTWljcm9zb2Z0IENvcnBvcmF0aW9uIEtFSyBDQSAyMDExMIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAxOi1ir-tVyawJsPq5_tXekQCXQcN2krldCrmsA_sbevsf7njWmMyfBEXTw7jC6c4FZOOxvXghLGamyzn9beR1gnh4sAEqKwwHN9I8wZQmmSnUX_IhU-PIIbO_i_hn_-CwO3pzc70U2piOgtDueIl_f4F-dTEFKsR4iOJjXC3pB1N7K7lnPoWwtfBy9ToxC_lme4kiwPsjfKL6sNK-0MREgt-tUeSbNzmBInr9TME6xABKnHl-YMTPP8lCS9odkb_uk--3K1xKliq-w7SeT3km2U7zCkqn_xyWaLrrpLv9jUTgMYC7ORfzJ12ze9jksGveUCEeYd_41Ko6J17B2mPFQIDAQABo4IBTzCCAUswEAYJKwYBBAGCNxUBBAMCAQAwHQYDVR0OBBYEFGL8Q82gPqTLZxLSW9lVrHvMtopfMBkGCSsGAQQBgjcUAgQMHgoAUwB1AGIAQwBBMAsGA1UdDwQEAwIBhjAPBgNVHRMBAf8EBTADAQH_MB8GA1UdIwQYMBaAFEVmUkPhflgRv9ZOniNVCDs6ImqoMFwGA1UdHwRVMFMwUaBPoE2GS2h0dHA6Ly9jcmwubWljcm9zb2Z0LmNvbS9wa2kvY3JsL3Byb2R1Y3RzL01pY0NvclRoaVBhck1hclJvb18yMDEwLTEwLTA1LmNybDBgBggrBgEFBQcBAQRUMFIwUAYIKwYBBQUHMAKGRGh0dHA6Ly93d3cubWljcm9zb2Z0LmNvbS9wa2kvY2VydHMvTWljQ29yVGhpUGFyTWFyUm9vXzIwMTAtMTAtMDUuY3J0MA0GCSqGSIb3DQEBCwUAA4ICAQDUhIj1FJQYAsoqPPsqkhwM16DR8ehSZqjuorV1epAAqi2kdlrqebe5N2pRexBk9uFk8gJnvveoG3i9us6IWGQM1lfIGaNfBdbbxtBpzkhLMrfrXdIw9cD1uLp4B6Mr_pvbNFaE7ILKrkElcJxr6f6QD9eWH-XnlB-yKgyNS_8oKRB799d8pdF2uQXIee0PkJKcwv7fb35sD3vUwUXdNFGWOQ_lXlbYGAWW9AemQrOgd_0IGfJxVsyfhiOkh8um_Vh-1GlnFZF-gfJ_E-UNi4o8h4Tr4869Q-WtLYSTjmorWnxE-lKqgcgtHLvgUt8AEfiaPcFgsOEztaOI0WUZChrnrHykwYKHTjixLw3FFIdv_Y0uvDm25-bD4OTNJ4TvlELvKYuQRkE7gRtn2PlDWWXLDbz9AJJP9HU7p6kk_FBBQHngLU8Kaid2blLtlml7rw_3hwXQRcKtUxSBH_swBKo3NmHaSmkbNNho7dYCz2yUDNPPbCJ5rbHwvAOiRmCpxAfCIYLx_fLoeTJgv9ispSIUS8rB2EvrfT9XNbLmT3W0sGADIlOukXkd1ptBHxWGVHCy3g01D3ywNHK6l2A78HnrorIcXaIWuIfF6Rv2tZclbzif45H6inmYw2kOt6McIAWX-MoUrgDXxPPAFBB1azSgG7WZYPNcsMVXTjbSMoS_njGCAcQwggHAAgEBMIGYMIGAMQswCQYDVQQGEwJVUzETMBEGA1UECBMKV2FzaGluZ3RvbjEQMA4GA1UEBxMHUmVkbW9uZDEeMBwGA1UEChMVTWljcm9zb2Z0IENvcnBvcmF0aW9uMSowKAYDVQQDEyFNaWNyb3NvZnQgQ29ycG9yYXRpb24gS0VLIENBIDIwMTECEzMAAAATa8knIN3tWYgAAAAAABMwDQYJYIZIAWUDBAIBBQAwDQYJKoZIhvcNAQEBBQAEggEAhabaxRIJ7nUZ-m__mIG0lII6yD-lxoeI8S83ZKTP8Qx5h5asySWl7420eGhna7zyaVRvVVIhkjOMIfcKr29LgzQpYDqPUc8aYAdGCsZKZGmHCMjEulnq5TDK79GKinzZfb2sAWXEJ68N8oNnY7faBKjHjmmJbAEz8ufE4DijgJ_NBov2xmhTZyNHQ7pB1iCdrEUGObzdJc0Qtmh3CNOEcmH0ukd8sTHE9acBBTFHS8dvreR_sP7dXClZJbJiWAFKvQn3EjCTiYizkZ4I_5xiqjHELht_ORQKN-Hnoqnl4kcRINhZRV7JlgAQDlBJLv3OTjShRO_ZWCdcu7PtwhweiSYWxMFMUJJArKlB-TaTQyiMDgAAAAAAADAAAAC9mvp3WQMyTb1gKPTnj3hLgLTZaTG_DQL9kaYeGdFPHaRS5m2yQIyoYE1BH5Jlnwq9mvp3WQMyTb1gKPTnj3hL9S-Do_qc-9aSD3IoJNvkA0U00luFByRrO5V9rG4bznq9mvp3WQMyTb1gKPTnj3hLxdnYoYbiyC0Jr6oqb38uc4cNPmT3LE4I72d5aoQPD729mvp3WQMyTb1gKPTnj3hLNjOE0U0fLgt4FWJkhMRZrVejGO9DliZgSNBYxaGbv3a9mvp3WQMyTb1gKPTnj3hLGuyEuEtsZaUSIKm-cYGWUjAhDWLW0zxImZxrKVorCga9mvp3WQMyTb1gKPTnj3hL5spo6UFGYprwP2nC-G5r72L5MLN8b7zIeLeN-YwDNOW9mvp3WQMyTb1gKPTnj3hLw6maRg2kZKBXw1htg8719K4ItxA5ee2JMnQt8O1TDGa9mvp3WQMyTb1gKPTnj3hLWPuUGu-VollDs_tfJRCg3z_kTFjJXgq4BIcpdWirl3G9mvp3WQMyTb1gKPTnj3hLU5HDovsRIQKmqh7cJa534Z9dbwnNCe6yUJkiv81Zkuq9mvp3WQMyTb1gKPTnj3hL1iYVfh1qcYvBJKuNony7ZQcsoDp7ayV9vcu9YPZe89G9mvp3WQMyTb1gKPTnj3hL0GPsKPZ-ulPxZC2_ff8zxqMq3YafYBP-Fi4sMvHL5W29mvp3WQMyTb1gKPTnj3hLKcbrUrQ8OqGLLNjtbqhgfO88-uG6_hFldVzy5hSESkS9mvp3WQMyTb1gKPTnj3hLkPvnDmnWM0CNPhcMaDLbstIJ4CclJ9-2PUnSlXKm9Ey9mvp3WQMyTb1gKPTnj3hLB17qBgWJVIugYLL-7RDaPCDH_psXzQJrlOimg7gRUji9mvp3WQMyTb1gKPTnj3hLB-bGqFhkb7HvxnkD_iixFgEfI2f-kua-KzaZnv850J69mvp3WQMyTb1gKPTnj3hLCd9fTlESCOx4uW0S0IEl_bYDho3jn29yknhSWZtlnCa9mvp3WQMyTb1gKPTnj3hLC7tDktqseribMKSsZXUxuXv6qwT5Cw2v5fm265CgY3S9mvp3WQMyTb1gKPTnj3hLDBiTOXYt8zarPdAGpGPfcVo5z7D0kkZcYA5sa9e9iYy9mvp3WQMyTb1gKPTnj3hLDQ2-ym8p7KBvMxp9cuSISxIJf7NImDoqFKDXP08QFA-9mvp3WQMyTb1gKPTnj3hLDcnz-5mWIUjDyoM2MnWNPtT8jQsAB7lbMeZSjyrNW_y9mvp3WQMyTb1gKPTnj3hLEG-s6s_s_U4wO3T0gKCAmOLQgCuTb47HdM4h8xaGaJy9mvp3WQMyTb1gKPTnj3hLF046C1tDxqYHu9NATwU0Hj3POWJnzpT4tQ4uI6nakgy9mvp3WQMyTb1gKPTnj3hLGDM0Kf8FYu2flwM-EUjc7uUtvi5JbVQQtc_WyGTS0Q-9mvp3WQMyTb1gKPTnj3hLK5nPJkIukv42X79Lww0nCGye4Ut6b_9E-y9rkAFpmTm9mvp3WQMyTb1gKPTnj3hLK78sp7jx2R8n7lK2-ypd0Em4WiubUpxdZmIGgQSwVfi9mvp3WQMyTb1gKPTnj3hLLHPZMyW6bcvlidSkxjxbk1VZ75L78FDtUMTiCFIG8X29mvp3WQMyTb1gKPTnj3hLLnCRZ4am93NRH6cYH6sPHXC1V8YyLqkjsqjTuStRr329mvp3WQMyTb1gKPTnj3hLMGYo-lR3MFcoukpGfefQOHpU9WnTdp_OXnXsidKNFZO9mvp3WQMyTb1gKPTnj3hLNgjtuvWtD0GkFKF3er8vr15nAzRnXsOZXmk1gp4MqtK9mvp3WQMyTb1gKPTnj3hLOEHSITaNFYPXXAoC5iFgOU1sTgpnYLb2B7kDYryFWwK9mvp3WQMyTb1gKPTnj3hLP86bn98-8J1UUrD5XuSBwrfwbXQ6c3lxVY5wE2rOPnO9mvp3WQMyTb1gKPTnj3hLQ5fayoOef2MHfLUMkt9DvC0vsqj1nyb8eg5L1Nl1FpK9mvp3WQMyTb1gKPTnj3hLR8wIYSfiBpqG4Dpr7yzUEPjFWm1r2zYhaMMbLOMqWt-9mvp3WQMyTb1gKPTnj3hLUYgx_nOCtRTQPhXGISKLirZUeb0Mv6PFwdD0jZwwYTW9mvp3WQMyTb1gKPTnj3hLWulJ6ohV65PkOdvGW9ouQoUsL99nifoUZzbjw0EPK1y9mvp3WQMyTb1gKPTnj3hLax0TgHjkQYqmjet7s14GYJLPR57rjOTNEufQcsy0L2a9mvp3WQMyTb1gKPTnj3hLbIhUR43VWeKTUbgmwGy4v-8rlK01ODWHctGT-C7RyhG9mvp3WQMyTb1gKPTnj3hLbxQo_3HJ2w7Vrx8ue7_Lq2R8wmXd9bKTzbYm9Qo6eF69mvp3WQMyTb1gKPTnj3hLcfKQb9IiSX5Uo0ZiqySX_MgQIHcP9RNo6ePZv8v9Y3W9mvp3WQMyTb1gKPTnj3hLcms-tlQEajDz-D2bls4D9nDpqAbRcIoDceYtxJ0sI8G9mvp3WQMyTb1gKPTnj3hLcuC9GGfPXZ1WqxWK3zvdvIK_MqjYqh2MXi9t8pQo1ti9mvp3WQMyTb1gKPTnj3hLeCevmTYs-vBxfa3ksb_gQ4rRccFa3cJIt1v4yqRLssW9mvp3WQMyTb1gKPTnj3hLgai5ZbuE04drlCmpVIHMlVMYz6oUEtgIyKM7_TP_8OS9mvp3WQMyTb1gKPTnj3hLgts7zrT2CEPOnZfD0YfNm1lBzT3oEA5YbyvaVjdXX2e9mvp3WQMyTb1gKPTnj3hLiVqXhfYXyh1-1E_BoUcLcfPxIjhi2f-dzDri35IWPa-9mvp3WQMyTb1gKPTnj3hLitZIWfGVtfWNr6qUC2phZ6zWeohuj0aTZBdyIcVZRbm9mvp3WQMyTb1gKPTnj3hLi_Q0tJ4AzPcVAqLNkAhlywHsOz2gPDW-UF_fe9Vj9SG9mvp3WQMyTb1gKPTnj3hLjY6iic_nChwHq3NlyyjuUe3TPPJQbeiI-63WDr-ASBy9mvp3WQMyTb1gKPTnj3hLmZjTY8SRvha9dLoQuU2SkQAWEXNv3KZDo2ZkvA8xWkK9mvp3WQMyTb1gKPTnj3hLnkppFzFhaC5V_ej-9WDriOwf_tyvBAAfZsDK9weytzS9mvp3WQMyTb1gKPTnj3hLprUVHzZV06KvDUcnWXlr5KQgDlSVp9hpdUxISIV0CKe9mvp3WQMyTb1gKPTnj3hLp_MvUI1OsP6tmgh--U7RugrsXeb372_wpiuTvt9dRY29mvp3WQMyTb1gKPTnj3hLrWgm4ZRtJtPq82hciNl9hd47Tcs9DuKugccFYNE8VyC9mvp3WQMyTb1gKPTnj3hLruuuMVEnEnPtlaouZxE57TGphWcwOjMimPg3CanVWqG9mvp3WQMyTb1gKPTnj3hLr-IDCvt9LNoT-fozOgLjT2dRr-wRsBDbzUQf30xAArO9mvp3WQMyTb1gKPTnj3hLtU8e5jZjH61oBY07CTcDGsG5DMsXBio5HMpor9vkDVW9mvp3WQMyTb1gKPTnj3hLuPB42YOiSsQzIWOTiDUUzZMsM68Y591wiEyCNfQnVza9mvp3WQMyTb1gKPTnj3hLuXoIiQWcA1_x1UtttTsRuXZmaNn5VSR8AosoN9egTNm9mvp3WQMyTb1gKPTnj3hLvIemaOgZZkictQjugFGDwZ5qzSTPF3mcoGLS44TaDqe9mvp3WQMyTb1gKPTnj3hLxAm9rEd1rdjbkqoitbcY-4yUoUYsH-mkFrldijOIwvy9mvp3WQMyTb1gKPTnj3hLxhfBqLHuKoEcKLWoG0yD18mLWwwnKB1hAgfr5pLCln-9mvp3WQMyTb1gKPTnj3hLyQ8zZhe45_mDl1QTyZfxC3PrJn_YoQy5472_xmer24u9mvp3WQMyTb1gKPTnj3hLy2uFi0DToJh2WBW1ksFRSklgT6_WCBnaiNenbpd4_ve9mvp3WQMyTb1gKPTnj3hLzjv6vlnWfOisjf1KFvfEPvnCJFE_vGVZV9c1-in1QM69mvp3WQMyTb1gKPTnj3hL2MvrlzX1Zys2fk-WzcdJaWFdFwdK6WxyTULOAhb48_q9mvp3WQMyTb1gKPTnj3hL6Swi6ztWQtZcHsLK8kfSWUc47rt_s4QaRJVvWeKw0fq9mvp3WQMyTb1gKPTnj3hL_d1uPSnqhMd0Pa1KG9vHALX-wbOR-TJAkIasxx3W29i9mvp3WQMyTb1gKPTnj3hL_mOoT3gsydP88sz5_BH70Ddgh4dY0mKF7RJmm9xubQG9mvp3WQMyTb1gKPTnj3hL_s-yMtEumUttSF0scWdyiqVSWYStXKYedRYiHweaFDa9mvp3WQMyTb1gKPTnj3hLyhcdYUqNfhIck5SM0P5V05mB-dEaqW4DRQpBUifCxlu9mvp3WQMyTb1gKPTnj3hLVbmbDeU9vP5IWqnHN88_thbvPZH6tZmqfKsZ7adjtbq9mvp3WQMyTb1gKPTnj3hLd90ZD6MNiP9eOwEaCuYeYgl4DBMLU17Lh-bwiIoLay-9mvp3WQMyTb1gKPTnj3hLyDyxOSKtmfVgdEZ13TfMlNytWh_Lpkcv7jQRcdk56IS9mvp3WQMyTb1gKPTnj3hLOwKHUz4Mw9DsGqgjy_CpQarYchV50cSZgC3Rw6Y2uKm9mvp3WQMyTb1gKPTnj3hLk5ru9PX6UeIzQMPy5JBIzohyUmr991LDp_Oj8ryfYEm9mvp3WQMyTb1gKPTnj3hLZFdb2RJ4mi4UrVb2NB9Sr2v4DPlEAHhZdenwTi1k10W9mvp3WQMyTb1gKPTnj3hLRcfIrnUKz7tI_DdSfWQS3WRNrtiRPM2KJMlNhWln344=",
              "fileType": "BIN"
            }
          ]
        },
        "source": "https://www.googleapis.com/compute/v1/projects/hydra-415522/zones/us-east1-c/disks/justicons-us-east1-c-vm",
        "type": "PERSISTENT"
      }
    ],
    "fingerprint": "HKmgeZdtmFI=",
    "id": "6319213131235773677",
    "kind": "compute#instance",
    "labelFingerprint": "54ffHQLiMnU=",
    "labels": {
      "goog-ec-src": "vm_add-gcloud"
    },
    "lastStartTimestamp": "2024-03-05T11:27:06.682-08:00",
    "machineType": "https://www.googleapis.com/compute/v1/projects/hydra-415522/zones/us-east1-c/machineTypes/e2-medium",
    "metadata": {
      "fingerprint": "G5lqf3wPCf4=",
      "items": [
        {
          "key": "enable-oslogin",
          "value": "true"
        },
        {
          "key": "ssh-keys",
          "value": "justiconsrunner:ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAINFUxJyYOV4crJxJk/UW3gLvCANAD/y1uwDZtmbduKcc daaronch@M1-Max.local\n"
        },
        {
          "key": "user-data",
          "value": "Content-Type: multipart/mixed; boundary=\"MIMEBOUNDARY\"\nMIME-Version: 1.0\r\n\r\n--MIMEBOUNDARY\r\nContent-Disposition: attachment; filename=\"cloud-config.yaml\"\r\nContent-Transfer-Encoding: 7bit\r\nContent-Type: text/cloud-config\r\nMime-Version: 1.0\r\n\r\n#cloud-config\npackages:\n  - git\n  - make\n  - curl\n  - gunicorn\n\nwrite_files:\n  - encoding: b64\n    content: |\n      IyEvYmluL2Jhc2gKIyBzaGVsbGNoZWNrIGRpc2FibGU9U0MxMDkxLFNDMjMxMixTQzIxNTUKc2V0IC1ldW8gcGlwZWZhaWwKSUZTPSQnXG5cdCcKCiMgd2Ugc3RhcnQgd2l0aCBub25lIGFzIHRoZSBkZWZhdWx0ICgibm9uZSIgcHJldmVudHMgdGhlIG5vZGUgY29ubmVjdGluZyB0byBvdXIgZGVmYXVsdCBib290c3RyYXAgbGlzdCkKZXhwb3J0IENPTk5FQ1RfUEVFUj0ibm9uZSIKCiMgU3BlY2lhbCBjYXNlIC0gZ2V0IHRhaWxzY2FsZSBhZGRyZXNzIGlmIGFueQojIElmIHRoZSB0YWlsc2NhbGUwIGFkZHJlc3MgZXhpc3RzIGluIHRoZSBjb21tYW5kIGlwCiMgR2V0IGludGVybmFsIElQIGFkZHJlc3MgZnJvbSB0aGUgZmlyc3QgcmVzdWx0IHRoYXQgc3RhcnRzIHdpdGggMTAuCmV4cG9ydCBJUD0kKGlwIC00IGFkZHIgc2hvdyB8IGdyZXAgLW9QICcoPzw9aW5ldFxzKVxkKyhcLlxkKyl7M30nIHwgZ3JlcCAtRSAnXjEwXC4nIHwgaGVhZCAtbiAxKQoKaWYgW1sgLW4gIiR7SVB9IiBdXTsgdGhlbgogIGV4cG9ydCBCQUNBTEhBVV9QUkVGRVJSRURfQUREUkVTUz0iJHtJUH0iCmZpCgojIGlmIHRoZSBmaWxlIC9ldGMvYmFjYWxoYXUtYm9vdHN0cmFwIGV4aXN0cywgdXNlIGl0IHRvIHBvcHVsYXRlIHRoZSBDT05ORUNUX1BFRVIgdmFyaWFibGUKaWYgW1sgLWYgL2V0Yy9iYWNhbGhhdS1ib290c3RyYXAgXV07IHRoZW4KICAjIHNoZWxsY2hlY2sgZGlzYWJsZT1TQzEwOTAKICBzb3VyY2UgL2V0Yy9iYWNhbGhhdS1ib290c3RyYXAKICBDT05ORUNUX1BFRVI9IiR7QkFDQUxIQVVfTk9ERV9MSUJQMlBfUEVFUkNPTk5FQ1R9IgpmaQoKIyBJZiAvZXRjL2JhY2FsaGF1LW5vZGUtaW5mbyBleGlzdHMsIHRoZW4gbG9hZCB0aGUgdmFyaWFibGVzIGZyb20gaXQKaWYgW1sgLWYgL2V0Yy9iYWNhbGhhdS1ub2RlLWluZm8gXV07IHRoZW4KICAjIHNoZWxsY2hlY2sgZGlzYWJsZT1TQzEwOTAKICAuIC9ldGMvYmFjYWxoYXUtbm9kZS1pbmZvCmZpCgpsYWJlbHM9ImlwPSR7SVB9IgoKIyBJZiBSRUdJT04gaXMgc2V0LCB0aGVuIHdlIGNhbiBhc3N1bWUgYWxsIGxhYmVscyBhcmUgc2V0LCBhbmQgd2Ugc2hvdWxkIGFkZCBpdCB0byB0aGUgbGFiZWxzCmlmIFtbIC1uICIke1JFR0lPTn0iIF1dOyB0aGVuCiAgbGFiZWxzPSIke2xhYmVsc30scmVnaW9uPSR7UkVHSU9OfSx6b25lPSR7Wk9ORX0sYXBwbmFtZT0ke0FQUE5BTUV9IgpmaQoKYmFjYWxoYXUgc2VydmUgXAogIC0tbm9kZS10eXBlIGNvbXB1dGUgXAogIC0tam9iLXNlbGVjdGlvbi1kYXRhLWxvY2FsaXR5IGFueXdoZXJlIFwKICAtLXN3YXJtLXBvcnQgMTIzNSBcCiAgLS1hcGktcG9ydCAxMjM0IFwKICAtLXBlZXIgIiR7Q09OTkVDVF9QRUVSfSIgXAogIC0tcHJpdmF0ZS1pbnRlcm5hbC1pcGZzPXRydWUgXAogIC0tam9iLXNlbGVjdGlvbi1hY2NlcHQtbmV0d29ya2VkIFwKICAtLWxhYmVscyAiJHtsYWJlbHN9Igo=\n    owner: root:root\n    path: /node/start-bacalhau.sh\n    permissions: \"0700\"\n  - encoding: b64\n    content: |\n      W1VuaXRdCkRlc2NyaXB0aW9uPUJhY2FsaGF1IERhZW1vbgpBZnRlcj1uZXR3b3JrLW9ubGluZS50YXJnZXQKV2FudHM9bmV0d29yay1vbmxpbmUudGFyZ2V0IHN5c3RlbWQtbmV0d29ya2Qtd2FpdC1vbmxpbmUuc2VydmljZQoKW1NlcnZpY2VdCkVudmlyb25tZW50PSJMT0dfVFlQRT1qc29uIgpFbnZpcm9ubWVudD0iQkFDQUxIQVVfUEFUSD0vZGF0YSIKRW52aXJvbm1lbnQ9IkJBQ0FMSEFVX0RJUj0vZGF0YSIKUmVzdGFydD1hbHdheXMKUmVzdGFydFNlYz01cwpFeGVjU3RhcnQ9YmFzaCAvbm9kZS9zdGFydC1iYWNhbGhhdS5zaAoKW0luc3RhbGxdCldhbnRlZEJ5PW11bHRpLXVzZXIudGFyZ2V0\n    owner: root:root\n    path: /etc/systemd/system/bacalhau.service\n    permissions: \"0600\"\n  - content: |\n      export PROJECT_ID=hydra-415522\n      export REGION=us-east1\n      export ZONE=us-east1-c\n      export APPNAME=justicons\n      export SITEURL=justicons.org\n      export TOKEN=8097a91e-bc5d-43db-889b-acd0dee618bc\n    owner: root:root\n    permissions: \"0444\"\n    path: /etc/bacalhau-node-info\n  - encoding: b64\n    content: |\n      IyEvdXNyL2Jpbi9lbnYgYmFzaApzZXQgLWUKc2V0IC14CgpleHBvcnQgRU5WRklMRT0iL2hvbWUvJHtBUFBVU0VSfS8uZW52IgoKc291cmNlICIke0VOVkZJTEV9IgoKYXB0IHVwZGF0ZQphcHQgaW5zdGFsbCAteSBnY2MgbWFrZSBwa2ctY29uZmlnIGxpYnNxbGl0ZTMtZGV2IGxpYmx6bWEtZGV2IGxpYmJ6Mi1kZXYgbGlibmN1cnNlczUtZGV2IGxpYmZmaS1kZXYgbGlicmVhZGxpbmUtZGV2IGxpYnNzbC1kZXYKCmFwdCBpbnN0YWxsIC15IHNvZnR3YXJlLXByb3BlcnRpZXMtY29tbW9uCmFkZC1hcHQtcmVwb3NpdG9yeSAteSBwcGE6ZGVhZHNuYWtlcy9wcGEKYXB0IHVwZGF0ZQphcHQgaW5zdGFsbCAteSBweXRob24zLjExIHB5dGhvbjMuMTEtdmVudiBweXRob24zLjExLWRpc3R1dGlscyBweXRob24zLjExLXRrCnVwZGF0ZS1hbHRlcm5hdGl2ZXMgLS1pbnN0YWxsIC91c3IvYmluL3B5dGhvbiBweXRob24gL3Vzci9iaW4vcHl0aG9uMy4xMSAwCmN1cmwgLXNTIGh0dHBzOi8vYm9vdHN0cmFwLnB5cGEuaW8vZ2V0LXBpcC5weSB8IHN1ZG8gcHl0aG9uMy4xMQoKIyBDbGVhbiB1cCBvbGQgZmlsZXMsIGp1c3QgdG8gYmUgc3VyZQpleHBvcnQgVVNFUkhPTUU9Ii9ob21lLyR7QVBQVVNFUn0iCmV4cG9ydCBQQVRIPSIke1VTRVJIT01FfS8ubG9jYWwvYmluOiR7UEFUSH0iCmV4cG9ydCBTRVRVUFZFTlZTQ1JJUFQ9IiR7VVNFUkhPTUV9L3NldHVwLXZlbnYuc2giCgplY2hvICJVU0VSSE9NRTogJHtVU0VSSE9NRX0iCmVjaG8gIkFQUFVTRVI6ICR7QVBQVVNFUn0iCmVjaG8gIkFQUERJUjogJHtBUFBESVJ9IgplY2hvICJQQVRIOiAke1BBVEh9IgoKZWNobyAiUnVubmluZyBzZXR1cC12ZW52LnNoIC4uLiIKcHVzaGQgJHtBUFBESVJ9CmNob3duIC1SICR7QVBQVVNFUn06JHtBUFBVU0VSfSAke1NFVFVQVkVOVlNDUklQVH0Kc3VkbyAtRSAtdSAke0FQUFVTRVJ9IGJhc2ggLWMgInNvdXJjZSAke0VOVkZJTEV9ICYmICR7U0VUVVBWRU5WU0NSSVBUfSIKcG9wZAoKbWtkaXIgLXAgL2V0Yy9zeXN0ZW1kL3N5c3RlbS9ndW5pY29ybi5zZXJ2aWNlLmQvCmNobW9kIDA3MDAgL2V0Yy9zeXN0ZW1kL3N5c3RlbS9ndW5pY29ybi5zZXJ2aWNlLmQvCgojIEd1bmljb3JuLnNlcnZpY2UKZWNobyAiQ3JlYXRpbmcgZ3VuaWNvcm4gbG9nIGRpcmVjdG9yaWVzLi4uIgpta2RpciAtcCAvdmFyL2xvZy9ndW5pY29ybgpjaG93biAke0FQUFVTRVJ9OiR7QVBQVVNFUn0gL3Zhci9sb2cvZ3VuaWNvcm4KCmVjaG8gIkNyZWF0aW5nIGd1bmljb3JuIHNlcnZpY2UgdW5pdC4uLiIKY2F0IDw8RU9GIHwgdGVlIC9ldGMvc3lzdGVtZC9zeXN0ZW0vZ3VuaWNvcm4uc2VydmljZSA+IC9kZXYvbnVsbApbVW5pdF0KRGVzY3JpcHRpb249Z3VuaWNvcm4gZGFlbW9uCkFmdGVyPW5ldHdvcmsudGFyZ2V0CgpbU2VydmljZV0KUGVybWlzc2lvbnNTdGFydE9ubHk9VHJ1ZQpUeXBlPW5vdGlmeQpVc2VyPSR7QVBQVVNFUn0KR3JvdXA9JHtBUFBVU0VSfQpXb3JraW5nRGlyZWN0b3J5PSR7QVBQRElSfQpFeGVjU3RhcnQ9JHtBUFBESVJ9LyR7UFlFTlZOQU1FfS9iaW4vZ3VuaWNvcm4gXAogICAgICAgICAgLS1hY2Nlc3MtbG9nZmlsZSAvdmFyL2xvZy9ndW5pY29ybi9hY2Nlc3MubG9nIFwKICAgICAgICAgIC0tZXJyb3ItbG9nZmlsZSAvdmFyL2xvZy9ndW5pY29ybi9lcnJvci5sb2cgXAogICAgICAgICAgLS10aW1lb3V0IDEyMCBcCiAgICAgICAgICAtLXdvcmtlcnMgMiBcCiAgICAgICAgICAtLWNoZGlyICR7QVBQRElSfSBcCiAgICAgICAgICAtYiAwLjAuMC4wOjE0MDQxIFwKICAgICAgICAgIC1iIFs6OjFdOjE2ODYxIFwKICAgICAgICAgIHdzZ2k6YXBwCkV4ZWNSZWxvYWQ9L2Jpbi9raWxsIC1zIEhVUCAkTUFJTlBJRApLaWxsTW9kZT1taXhlZApUaW1lb3V0U3RvcFNlYz01ClByaXZhdGVUbXA9dHJ1ZQoKW0luc3RhbGxdCldhbnRlZEJ5PW11bHRpLXVzZXIudGFyZ2V0CkVPRgoKZWNobyAiUmVzdGFydGluZyBndW5pY29ybiBsb2cgcm90YXRlcnMgLi4uIgpjYXQgPDxFT0YgfCB0ZWUgL2V0Yy9sb2dyb3RhdGUuZC9ndW5pY29ybiA+IC9kZXYvbnVsbAovdmFyL2xvZy9ndW5pY29ybi8qLmxvZyB7CglkYWlseQoJbWlzc2luZ29rCglyb3RhdGUgMTQKCWNvbXByZXNzCglub3RpZmVtcHR5CgljcmVhdGUgMDY0MCAke0FQUFVTRVJ9ICR7QVBQVVNFUn0KCXNoYXJlZHNjcmlwdHMKCXBvc3Ryb3RhdGUKCQlzeXN0ZW1jdGwgcmVsb2FkIGd1bmljb3JuCgllbmRzY3JpcHQKfQpFT0YKCmVjaG8gIlJlc3RhcnRpbmcgYWxsIHNlcnZpY2VzIC4uLiAiCnN1ZG8gc3lzdGVtY3RsIGVuYWJsZSBndW5pY29ybi5zZXJ2aWNlCgpzeXN0ZW1jdGwgZGFlbW9uLXJlbG9hZApzeXN0ZW1jdGwgcmVzdGFydCBndW5pY29ybgplY2hvICJEb25lIHdpdGggR3VuaWNvcm4uIgoKZWNobyAiSW5zdGFsbGluZyBsaWdodGh0dHBkIGZvciBoZWFydGJlYXQiCmFwdCBpbnN0YWxsIC15IGxpZ2h0dHBkCnN5c3RlbWN0bCByZXN0YXJ0IGxpZ2h0dHBkCmVjaG8gLW4gIm9rIiB8IHN1ZG8gdGVlIC92YXIvd3d3L2h0bWwvaW5kZXgubGlnaHR0cGQuaHRtbCA+IC9kZXYvbnVsbAoKIyBQaW5nIGl0c2FkYXNoLndvcmsvdXBkYXRlX3NpdGVzIHdpdGggYSBqc29uIG9mIHRoZSBmb3JtIHsic2l0ZSI6ICJzaXRlX25hbWUiLCAiaXAiOiAiaXBfYWRkcmVzcyJ9CmVjaG8gIlBpbmdpbmcgaXRzYWRhc2gud29yay91cGRhdGUgLi4uIgpleHBvcnQgUFJJVkFURUlQPSQoaXAgYWRkciB8IGF3ayAnL2luZXQvICYmIC8xMFwuLyB7c3BsaXQoJDIsIGlwLCAiLyIpOyBwcmludCBpcFsxXX0nKQpjdXJsIC1YIFBPU1QgLUggIkNvbnRlbnQtVHlwZTogYXBwbGljYXRpb24vanNvbiIgLWQgIntcInNpdGVcIjogXCIke1NJVEVVUkx9XCIsIFwiVE9LRU5cIjogXCIke1RPS0VOfVwiLCBcIlNFUlZFUklQXCI6IFwiJHtQUklWQVRFSVB9XCIgIH0iIGh0dHA6Ly9pdHNhZGFzaC53b3JrL3VwZGF0ZQo=\n    owner: root:root\n    path: /node/install-gunicorn-service.sh\n    permissions: \"0700\"\n  - encoding: b64\n    content: |\n      IyEvdXNyL2Jpbi9lbnYgYmFzaApzZXQgLWUKc2V0IC14CgojIEVuc3VyZSBwb2V0cnkgaXMgaW5zdGFsbGVkCnB5dGhvbiAtbSBwaXAgaW5zdGFsbCAtLXVzZXIgcG9ldHJ5CgojIElmICRBUFBESVIgZG9lcyBub3QgZXhpc3QgdGhlbiBjcmVhdGUgaXQKaWYgWyAhIC1kICIkQVBQRElSIiBdOyB0aGVuCiAgICBta2RpciAtcCAiJEFQUERJUiIKZmkKCmNkICIkQVBQRElSIiB8fCBleGl0CgojIElmIHB5cHJvamVjdC50b21sIGlzbid0IHRoZXJlIHRoZW4gY29weSB0aGUgYXBwIGZpbGVzIGZyb20gL3RtcAoKIyBJbnN0YWxsIHBvZXRyeS1wbHVnaW4tZXhwb3J0CnB5dGhvbiAtbSBwaXAgaW5zdGFsbCAtLXVzZXIgcG9ldHJ5LXBsdWdpbi1leHBvcnQKCiMgRXhwb3J0IGRlcGVuZGVuY2llcyB0byByZXF1aXJlbWVudHMudHh0CnB5dGhvbiAtbSBwb2V0cnkgZXhwb3J0IC0td2l0aG91dC1oYXNoZXMgLS1mb3JtYXQ9cmVxdWlyZW1lbnRzLnR4dCA+IHJlcXVpcmVtZW50cy50eHQKCiMgSW5zdGFsbCB2aXJ0dWFsZW52CnB5dGhvbiAtbSBwaXAgaW5zdGFsbCAtLXVzZXIgdmlydHVhbGVudgoKIyBDcmVhdGUgYW5kIGFjdGl2YXRlIHZpcnR1YWwgZW52aXJvbm1lbnQKcHl0aG9uIC1tIHZlbnYgIiR7UFlFTlZOQU1FfSIKc291cmNlICIke1BZRU5WTkFNRX0vYmluL2FjdGl2YXRlIgoKIyBJbnN0YWxsIFB5dGhvbiBkZXBlbmRlbmNpZXMgZnJvbSByZXF1aXJlbWVudHMudHh0CnB5dGhvbiAtbSBwaXAgaW5zdGFsbCAtciByZXF1aXJlbWVudHMudHh0CgojIERlYWN0aXZhdGUgdmlydHVhbCBlbnZpcm9ubWVudApkZWFjdGl2YXRlCg==\n    path: /tmp/rsync/justiconsrunner/setup-venv.sh\n    permissions: \"0700\"\n  - content: |\n      APPUSER=justiconsrunner\n      APPDIR=/home/justiconsrunner/justiconsapp\n      PYENVNAME=justiconsvenv\n      SITEURL=justicons.org\n      TOKEN=8097a91e-bc5d-43db-889b-acd0dee618bc\n    permissions: \"0444\"\n    path: /tmp/rsync/justiconsrunner/.env\n  - encoding: b64\n    content: |\n      ZXhwb3J0IEJBQ0FMSEFVX05PREVfQ0xJRU5UQVBJX0hPU1Q9MTAuMTI4LjAuMgpleHBvcnQgQkFDQUxIQVVfTk9ERV9DTElFTlRBUElfUE9SVD0xMjM0CmV4cG9ydCBCQUNBTEhBVV9OT0RFX05FVFdPUktfVFlQRT1saWJwMnAKZXhwb3J0IEJBQ0FMSEFVX05PREVfTElCUDJQX1BFRVJDT05ORUNUPS9pcDQvMTAuMTI4LjAuMi90Y3AvMTIzNS9wMnAvUW1ROUxXRnNwakJNMWI4d00yWVdkdFF3M3hGNFhVZW1qWml0S3E5cmRleFN5WQpleHBvcnQgQkFDQUxIQVVfTk9ERV9JUEZTX1NXQVJNQUREUkVTU0VTPS9pcDQvMTAuMTI4LjAuMi90Y3AvNDEwMTEvcDJwL1FtUkxoMU5QdjNKc0ZERmszTnlxRFV1NTF3Q21VSzUzazcyc1N1OU5URHRLWUYK\n    owner: root:root\n    path: /etc/bacalhau-bootstrap\n    permissions: \"0400\"\n\npackage_update: true\n\nruncmd:\n  - echo \"Copying the SSH Key to the server\"\n  - |\n    echo -n \"ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAINFUxJyYOV4crJxJk/UW3gLvCANAD/y1uwDZtmbduKcc daaronch@M1-Max.local\" | awk 1 ORS=' ' >> /root/.ssh/authorized_keys\n  - sudo useradd --create-home -r justiconsrunner -s /usr/bin/bash || echo 'User already exists.'\n  #\n  # Make node directory for all scripts\n  #\n  - mkdir -p /node\n  - chmod 0700 /node\n  - mkdir -p /data\n  - chmod 0700 /data\n  #\n  # Install docker\n  #\n  - sudo apt-get install -y ca-certificates curl gnupg lsb-release\n  - sudo mkdir -p /etc/apt/keyrings\n  - |\n    curl -fsSL \"https://download.docker.com/linux/ubuntu/gpg\" | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg\n    echo \"deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable\" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null\n  - sudo apt-get update -y\n  - sudo apt -y install docker-ce docker-ce-cli containerd.io docker-compose-plugin\n  #\n  # Install Bacalhau\n  #\n  - |\n    curl -sL https://get.bacalhau.org/install.sh | BACALHAU_DIR=/$GENHOME/data bash\n  - echo \"Bacalhau downloaded.\"\n  #\n  # Sync from /tmp\n  #\n  - rsync --no-relative /tmp/rsync/justiconsrunner/setup-venv.sh /home/justiconsrunner\n  - rsync --no-relative /tmp/rsync/justiconsrunner/.env /home/justiconsrunner\n  - rm -rf /tmp/rsync\n  #\n  # Install the gunicorn service\n  #\n  - git clone https://github.com/bacalhau-project/examples.git /tmp/web-control-plane\n  - (cd /tmp/web-control-plane && git checkout web-control-plane)\n  - rsync -av --no-relative /tmp/web-control-plane/case-studies/web-control-plane/justicons/client/* /home/justiconsrunner/justiconsapp\n  - chown -R justiconsrunner:justiconsrunner /home/justiconsrunner/justiconsapp\n  - env $(cat /home/justiconsrunner/.env | xargs) /node/install-gunicorn-service.sh\n  -\n  # Reload the systemd daemon, enable, and start the service\n  - sudo sysctl -w net.core.rmem_max=2500000\n  - sudo systemctl daemon-reload\n  - sudo systemctl enable docker\n  - sudo systemctl restart docker\n  - sudo systemctl enable bacalhau.service\n  - sudo systemctl restart bacalhau.service\n  - sleep 20 # Give the log generator a chance to start - and then force generate four entries\n\r\n--MIMEBOUNDARY--\r\n"
        }
      ],
      "kind": "compute#metadata"
    },
    "name": "justicons-us-east1-c-vm",
    "networkInterfaces": [
      {
        "accessConfigs": [
          {
            "kind": "compute#accessConfig",
            "name": "external-nat",
            "natIP": "34.138.240.222",
            "networkTier": "PREMIUM",
            "type": "ONE_TO_ONE_NAT"
          }
        ],
        "fingerprint": "IjsSXuNooyw=",
        "kind": "compute#networkInterface",
        "name": "nic0",
        "network": "https://www.googleapis.com/compute/v1/projects/hydra-415522/global/networks/global-network",
        "networkIP": "10.142.0.43",
        "stackType": "IPV4_ONLY",
        "subnetwork": "https://www.googleapis.com/compute/v1/projects/hydra-415522/regions/us-east1/subnetworks/global-network"
      }
    ],
    "scheduling": {
      "automaticRestart": true,
      "onHostMaintenance": "MIGRATE",
      "preemptible": false,
      "provisioningModel": "STANDARD"
    },
    "selfLink": "https://www.googleapis.com/compute/v1/projects/hydra-415522/zones/us-east1-c/instances/justicons-us-east1-c-vm",
    "serviceAccounts": [
      {
        "email": "hydra-415522-sa@hydra-415522.iam.gserviceaccount.com",
        "scopes": [
          "https://www.googleapis.com/auth/cloud-platform"
        ]
      }
    ],
    "shieldedInstanceConfig": {
      "enableIntegrityMonitoring": true,
      "enableSecureBoot": false,
      "enableVtpm": true
    },
    "shieldedInstanceIntegrityPolicy": {
      "updateAutoLearnPolicy": true
    },
    "startRestricted": false,
    "status": "RUNNING",
    "tags": {
      "fingerprint": "jqy-0AEP0r0=",
      "items": [
        "allow-bacalhau",
        "allow-ssh",
        "default-allow-internal"
      ]
    },
    "zone": "https://www.googleapis.com/compute/v1/projects/hydra-415522/zones/us-east1-c"
  },
  {
    "canIpForward": false,
    "cpuPlatform": "Intel Broadwell",
    "creationTimestamp": "2024-03-05T11:26:59.319-08:00",
    "deletionProtection": false,
    "disks": [
      {
        "architecture": "X86_64",
        "autoDelete": true,
        "boot": true,
        "deviceName": "persistent-disk-0",
        "diskSizeGb": "10",
        "guestOsFeatures": [
          {
            "type": "VIRTIO_SCSI_MULTIQUEUE"
          },
          {
            "type": "SEV_CAPABLE"
          },
          {
            "type": "SEV_SNP_CAPABLE"
          },
          {
            "type": "SEV_LIVE_MIGRATABLE"
          },
          {
            "type": "SEV_LIVE_MIGRATABLE_V2"
          },
          {
            "type": "IDPF"
          },
          {
            "type": "UEFI_COMPATIBLE"
          },
          {
            "type": "GVNIC"
          }
        ],
        "index": 0,
        "interface": "SCSI",
        "kind": "compute#attachedDisk",
        "licenses": [
          "https://www.googleapis.com/compute/v1/projects/ubuntu-os-cloud/global/licenses/ubuntu-2204-lts"
        ],
        "mode": "READ_WRITE",
        "shieldedInstanceInitialState": {
          "dbxs": [
            {
              "content": "2gcDBhMRFQAAAAAAAAAAABENAAAAAvEOndKvSt9o7kmKqTR9N1ZlpzCCDPUCAQExDzANBglghkgBZQMEAgEFADALBgkqhkiG9w0BBwGgggsIMIIFGDCCBACgAwIBAgITMwAAABNryScg3e1ZiAAAAAAAEzANBgkqhkiG9w0BAQsFADCBgDELMAkGA1UEBhMCVVMxEzARBgNVBAgTCldhc2hpbmd0b24xEDAOBgNVBAcTB1JlZG1vbmQxHjAcBgNVBAoTFU1pY3Jvc29mdCBDb3Jwb3JhdGlvbjEqMCgGA1UEAxMhTWljcm9zb2Z0IENvcnBvcmF0aW9uIEtFSyBDQSAyMDExMB4XDTE2MDEwNjE4MzQxNVoXDTE3MDQwNjE4MzQxNVowgZUxCzAJBgNVBAYTAlVTMRMwEQYDVQQIEwpXYXNoaW5ndG9uMRAwDgYDVQQHEwdSZWRtb25kMR4wHAYDVQQKExVNaWNyb3NvZnQgQ29ycG9yYXRpb24xDTALBgNVBAsTBE1PUFIxMDAuBgNVBAMTJ01pY3Jvc29mdCBXaW5kb3dzIFVFRkkgS2V5IEV4Y2hhbmdlIEtleTCCASIwDQYJKoZIhvcNAQEBBQADggEPADCCAQoCggEBAKXiCkZgbboTnVZnS1h_JbnlcVst9wtFK8NQjTpeB9wirml3h-fzi8vzki0hSNBD2Dg49lGEvs4egyowmTsLu1TnBUH1f_Hi8Noa7fKXV6F93qYrTPajx5v9L7NedplWnMEPsRvJrQdrysTZwtoXMLYDhc8bQHI5nlJDfgqrB8JiC4A3vL9i19lkQOTq4PZb5AcVcE0wlG7lR_btoQN0g5B4_7pI2S_9mU1PXr1NBSEl48Kl4cJwO2GyvOVvxQ6wUSFTExmCBKrT3LnPU5lZY68n3MpZ5VY4skhrEt2dyf5bZNzkYTTouxC0n37OrMbGGq3tpv7JDD6E_Rfqua3dXYECAwEAAaOCAXIwggFuMBQGA1UdJQQNMAsGCSsGAQQBgjdPATAdBgNVHQ4EFgQUVsJIppTfox2XYoAJRIlnxAUOy2owUQYDVR0RBEowSKRGMEQxDTALBgNVBAsTBE1PUFIxMzAxBgNVBAUTKjMxNjMxKzJjNDU2Y2JjLTA1NDItNDdkOS05OWU1LWQzOWI4MTVjNTczZTAfBgNVHSMEGDAWgBRi_EPNoD6ky2cS0lvZVax7zLaKXzBTBgNVHR8ETDBKMEigRqBEhkJodHRwOi8vd3d3Lm1pY3Jvc29mdC5jb20vcGtpb3BzL2NybC9NaWNDb3JLRUtDQTIwMTFfMjAxMS0wNi0yNC5jcmwwYAYIKwYBBQUHAQEEVDBSMFAGCCsGAQUFBzAChkRodHRwOi8vd3d3Lm1pY3Jvc29mdC5jb20vcGtpb3BzL2NlcnRzL01pY0NvcktFS0NBMjAxMV8yMDExLTA2LTI0LmNydDAMBgNVHRMBAf8EAjAAMA0GCSqGSIb3DQEBCwUAA4IBAQCGjTFLjxsKmyLESJueg0S2Cp8N7MOq2IALsitZHwfYw2jMhY9b9kmKvIdSqVna1moZ6_zJSOS_JY6HkWZr6dDJe9Lj7xiW_e4qPP-KDrCVb02vBnK4EktVjTdJpyMhxBMdXUcq1eGl6518oCkQ27tu0-WZjaWEVsEY_gpQj0ye2UA4HYUYgJlpT24oJRi7TeQ03Nebb-ZrUkbf9uxl0OVV_mg2R5FDwOc3REoRAgv5jnw6X7ha5hlRCl2cLF27TFrFIRQQT4eSM33eDiitXXpYmD13jqKeHhLVXr07QSwqvKe1o1UYokJngP0pTwoDnt2qRuLnZ71jw732dSPN9B57MIIF6DCCA9CgAwIBAgIKYQrRiAAAAAAAAzANBgkqhkiG9w0BAQsFADCBkTELMAkGA1UEBhMCVVMxEzARBgNVBAgTCldhc2hpbmd0b24xEDAOBgNVBAcTB1JlZG1vbmQxHjAcBgNVBAoTFU1pY3Jvc29mdCBDb3Jwb3JhdGlvbjE7MDkGA1UEAxMyTWljcm9zb2Z0IENvcnBvcmF0aW9uIFRoaXJkIFBhcnR5IE1hcmtldHBsYWNlIFJvb3QwHhcNMTEwNjI0MjA0MTI5WhcNMjYwNjI0MjA1MTI5WjCBgDELMAkGA1UEBhMCVVMxEzARBgNVBAgTCldhc2hpbmd0b24xEDAOBgNVBAcTB1JlZG1vbmQxHjAcBgNVBAoTFU1pY3Jvc29mdCBDb3Jwb3JhdGlvbjEqMCgGA1UEAxMhTWljcm9zb2Z0IENvcnBvcmF0aW9uIEtFSyBDQSAyMDExMIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAxOi1ir-tVyawJsPq5_tXekQCXQcN2krldCrmsA_sbevsf7njWmMyfBEXTw7jC6c4FZOOxvXghLGamyzn9beR1gnh4sAEqKwwHN9I8wZQmmSnUX_IhU-PIIbO_i_hn_-CwO3pzc70U2piOgtDueIl_f4F-dTEFKsR4iOJjXC3pB1N7K7lnPoWwtfBy9ToxC_lme4kiwPsjfKL6sNK-0MREgt-tUeSbNzmBInr9TME6xABKnHl-YMTPP8lCS9odkb_uk--3K1xKliq-w7SeT3km2U7zCkqn_xyWaLrrpLv9jUTgMYC7ORfzJ12ze9jksGveUCEeYd_41Ko6J17B2mPFQIDAQABo4IBTzCCAUswEAYJKwYBBAGCNxUBBAMCAQAwHQYDVR0OBBYEFGL8Q82gPqTLZxLSW9lVrHvMtopfMBkGCSsGAQQBgjcUAgQMHgoAUwB1AGIAQwBBMAsGA1UdDwQEAwIBhjAPBgNVHRMBAf8EBTADAQH_MB8GA1UdIwQYMBaAFEVmUkPhflgRv9ZOniNVCDs6ImqoMFwGA1UdHwRVMFMwUaBPoE2GS2h0dHA6Ly9jcmwubWljcm9zb2Z0LmNvbS9wa2kvY3JsL3Byb2R1Y3RzL01pY0NvclRoaVBhck1hclJvb18yMDEwLTEwLTA1LmNybDBgBggrBgEFBQcBAQRUMFIwUAYIKwYBBQUHMAKGRGh0dHA6Ly93d3cubWljcm9zb2Z0LmNvbS9wa2kvY2VydHMvTWljQ29yVGhpUGFyTWFyUm9vXzIwMTAtMTAtMDUuY3J0MA0GCSqGSIb3DQEBCwUAA4ICAQDUhIj1FJQYAsoqPPsqkhwM16DR8ehSZqjuorV1epAAqi2kdlrqebe5N2pRexBk9uFk8gJnvveoG3i9us6IWGQM1lfIGaNfBdbbxtBpzkhLMrfrXdIw9cD1uLp4B6Mr_pvbNFaE7ILKrkElcJxr6f6QD9eWH-XnlB-yKgyNS_8oKRB799d8pdF2uQXIee0PkJKcwv7fb35sD3vUwUXdNFGWOQ_lXlbYGAWW9AemQrOgd_0IGfJxVsyfhiOkh8um_Vh-1GlnFZF-gfJ_E-UNi4o8h4Tr4869Q-WtLYSTjmorWnxE-lKqgcgtHLvgUt8AEfiaPcFgsOEztaOI0WUZChrnrHykwYKHTjixLw3FFIdv_Y0uvDm25-bD4OTNJ4TvlELvKYuQRkE7gRtn2PlDWWXLDbz9AJJP9HU7p6kk_FBBQHngLU8Kaid2blLtlml7rw_3hwXQRcKtUxSBH_swBKo3NmHaSmkbNNho7dYCz2yUDNPPbCJ5rbHwvAOiRmCpxAfCIYLx_fLoeTJgv9ispSIUS8rB2EvrfT9XNbLmT3W0sGADIlOukXkd1ptBHxWGVHCy3g01D3ywNHK6l2A78HnrorIcXaIWuIfF6Rv2tZclbzif45H6inmYw2kOt6McIAWX-MoUrgDXxPPAFBB1azSgG7WZYPNcsMVXTjbSMoS_njGCAcQwggHAAgEBMIGYMIGAMQswCQYDVQQGEwJVUzETMBEGA1UECBMKV2FzaGluZ3RvbjEQMA4GA1UEBxMHUmVkbW9uZDEeMBwGA1UEChMVTWljcm9zb2Z0IENvcnBvcmF0aW9uMSowKAYDVQQDEyFNaWNyb3NvZnQgQ29ycG9yYXRpb24gS0VLIENBIDIwMTECEzMAAAATa8knIN3tWYgAAAAAABMwDQYJYIZIAWUDBAIBBQAwDQYJKoZIhvcNAQEBBQAEggEAhabaxRIJ7nUZ-m__mIG0lII6yD-lxoeI8S83ZKTP8Qx5h5asySWl7420eGhna7zyaVRvVVIhkjOMIfcKr29LgzQpYDqPUc8aYAdGCsZKZGmHCMjEulnq5TDK79GKinzZfb2sAWXEJ68N8oNnY7faBKjHjmmJbAEz8ufE4DijgJ_NBov2xmhTZyNHQ7pB1iCdrEUGObzdJc0Qtmh3CNOEcmH0ukd8sTHE9acBBTFHS8dvreR_sP7dXClZJbJiWAFKvQn3EjCTiYizkZ4I_5xiqjHELht_ORQKN-Hnoqnl4kcRINhZRV7JlgAQDlBJLv3OTjShRO_ZWCdcu7PtwhweiSYWxMFMUJJArKlB-TaTQyiMDgAAAAAAADAAAAC9mvp3WQMyTb1gKPTnj3hLgLTZaTG_DQL9kaYeGdFPHaRS5m2yQIyoYE1BH5Jlnwq9mvp3WQMyTb1gKPTnj3hL9S-Do_qc-9aSD3IoJNvkA0U00luFByRrO5V9rG4bznq9mvp3WQMyTb1gKPTnj3hLxdnYoYbiyC0Jr6oqb38uc4cNPmT3LE4I72d5aoQPD729mvp3WQMyTb1gKPTnj3hLNjOE0U0fLgt4FWJkhMRZrVejGO9DliZgSNBYxaGbv3a9mvp3WQMyTb1gKPTnj3hLGuyEuEtsZaUSIKm-cYGWUjAhDWLW0zxImZxrKVorCga9mvp3WQMyTb1gKPTnj3hL5spo6UFGYprwP2nC-G5r72L5MLN8b7zIeLeN-YwDNOW9mvp3WQMyTb1gKPTnj3hLw6maRg2kZKBXw1htg8719K4ItxA5ee2JMnQt8O1TDGa9mvp3WQMyTb1gKPTnj3hLWPuUGu-VollDs_tfJRCg3z_kTFjJXgq4BIcpdWirl3G9mvp3WQMyTb1gKPTnj3hLU5HDovsRIQKmqh7cJa534Z9dbwnNCe6yUJkiv81Zkuq9mvp3WQMyTb1gKPTnj3hL1iYVfh1qcYvBJKuNony7ZQcsoDp7ayV9vcu9YPZe89G9mvp3WQMyTb1gKPTnj3hL0GPsKPZ-ulPxZC2_ff8zxqMq3YafYBP-Fi4sMvHL5W29mvp3WQMyTb1gKPTnj3hLKcbrUrQ8OqGLLNjtbqhgfO88-uG6_hFldVzy5hSESkS9mvp3WQMyTb1gKPTnj3hLkPvnDmnWM0CNPhcMaDLbstIJ4CclJ9-2PUnSlXKm9Ey9mvp3WQMyTb1gKPTnj3hLB17qBgWJVIugYLL-7RDaPCDH_psXzQJrlOimg7gRUji9mvp3WQMyTb1gKPTnj3hLB-bGqFhkb7HvxnkD_iixFgEfI2f-kua-KzaZnv850J69mvp3WQMyTb1gKPTnj3hLCd9fTlESCOx4uW0S0IEl_bYDho3jn29yknhSWZtlnCa9mvp3WQMyTb1gKPTnj3hLC7tDktqseribMKSsZXUxuXv6qwT5Cw2v5fm265CgY3S9mvp3WQMyTb1gKPTnj3hLDBiTOXYt8zarPdAGpGPfcVo5z7D0kkZcYA5sa9e9iYy9mvp3WQMyTb1gKPTnj3hLDQ2-ym8p7KBvMxp9cuSISxIJf7NImDoqFKDXP08QFA-9mvp3WQMyTb1gKPTnj3hLDcnz-5mWIUjDyoM2MnWNPtT8jQsAB7lbMeZSjyrNW_y9mvp3WQMyTb1gKPTnj3hLEG-s6s_s_U4wO3T0gKCAmOLQgCuTb47HdM4h8xaGaJy9mvp3WQMyTb1gKPTnj3hLF046C1tDxqYHu9NATwU0Hj3POWJnzpT4tQ4uI6nakgy9mvp3WQMyTb1gKPTnj3hLGDM0Kf8FYu2flwM-EUjc7uUtvi5JbVQQtc_WyGTS0Q-9mvp3WQMyTb1gKPTnj3hLK5nPJkIukv42X79Lww0nCGye4Ut6b_9E-y9rkAFpmTm9mvp3WQMyTb1gKPTnj3hLK78sp7jx2R8n7lK2-ypd0Em4WiubUpxdZmIGgQSwVfi9mvp3WQMyTb1gKPTnj3hLLHPZMyW6bcvlidSkxjxbk1VZ75L78FDtUMTiCFIG8X29mvp3WQMyTb1gKPTnj3hLLnCRZ4am93NRH6cYH6sPHXC1V8YyLqkjsqjTuStRr329mvp3WQMyTb1gKPTnj3hLMGYo-lR3MFcoukpGfefQOHpU9WnTdp_OXnXsidKNFZO9mvp3WQMyTb1gKPTnj3hLNgjtuvWtD0GkFKF3er8vr15nAzRnXsOZXmk1gp4MqtK9mvp3WQMyTb1gKPTnj3hLOEHSITaNFYPXXAoC5iFgOU1sTgpnYLb2B7kDYryFWwK9mvp3WQMyTb1gKPTnj3hLP86bn98-8J1UUrD5XuSBwrfwbXQ6c3lxVY5wE2rOPnO9mvp3WQMyTb1gKPTnj3hLQ5fayoOef2MHfLUMkt9DvC0vsqj1nyb8eg5L1Nl1FpK9mvp3WQMyTb1gKPTnj3hLR8wIYSfiBpqG4Dpr7yzUEPjFWm1r2zYhaMMbLOMqWt-9mvp3WQMyTb1gKPTnj3hLUYgx_nOCtRTQPhXGISKLirZUeb0Mv6PFwdD0jZwwYTW9mvp3WQMyTb1gKPTnj3hLWulJ6ohV65PkOdvGW9ouQoUsL99nifoUZzbjw0EPK1y9mvp3WQMyTb1gKPTnj3hLax0TgHjkQYqmjet7s14GYJLPR57rjOTNEufQcsy0L2a9mvp3WQMyTb1gKPTnj3hLbIhUR43VWeKTUbgmwGy4v-8rlK01ODWHctGT-C7RyhG9mvp3WQMyTb1gKPTnj3hLbxQo_3HJ2w7Vrx8ue7_Lq2R8wmXd9bKTzbYm9Qo6eF69mvp3WQMyTb1gKPTnj3hLcfKQb9IiSX5Uo0ZiqySX_MgQIHcP9RNo6ePZv8v9Y3W9mvp3WQMyTb1gKPTnj3hLcms-tlQEajDz-D2bls4D9nDpqAbRcIoDceYtxJ0sI8G9mvp3WQMyTb1gKPTnj3hLcuC9GGfPXZ1WqxWK3zvdvIK_MqjYqh2MXi9t8pQo1ti9mvp3WQMyTb1gKPTnj3hLeCevmTYs-vBxfa3ksb_gQ4rRccFa3cJIt1v4yqRLssW9mvp3WQMyTb1gKPTnj3hLgai5ZbuE04drlCmpVIHMlVMYz6oUEtgIyKM7_TP_8OS9mvp3WQMyTb1gKPTnj3hLgts7zrT2CEPOnZfD0YfNm1lBzT3oEA5YbyvaVjdXX2e9mvp3WQMyTb1gKPTnj3hLiVqXhfYXyh1-1E_BoUcLcfPxIjhi2f-dzDri35IWPa-9mvp3WQMyTb1gKPTnj3hLitZIWfGVtfWNr6qUC2phZ6zWeohuj0aTZBdyIcVZRbm9mvp3WQMyTb1gKPTnj3hLi_Q0tJ4AzPcVAqLNkAhlywHsOz2gPDW-UF_fe9Vj9SG9mvp3WQMyTb1gKPTnj3hLjY6iic_nChwHq3NlyyjuUe3TPPJQbeiI-63WDr-ASBy9mvp3WQMyTb1gKPTnj3hLmZjTY8SRvha9dLoQuU2SkQAWEXNv3KZDo2ZkvA8xWkK9mvp3WQMyTb1gKPTnj3hLnkppFzFhaC5V_ej-9WDriOwf_tyvBAAfZsDK9weytzS9mvp3WQMyTb1gKPTnj3hLprUVHzZV06KvDUcnWXlr5KQgDlSVp9hpdUxISIV0CKe9mvp3WQMyTb1gKPTnj3hLp_MvUI1OsP6tmgh--U7RugrsXeb372_wpiuTvt9dRY29mvp3WQMyTb1gKPTnj3hLrWgm4ZRtJtPq82hciNl9hd47Tcs9DuKugccFYNE8VyC9mvp3WQMyTb1gKPTnj3hLruuuMVEnEnPtlaouZxE57TGphWcwOjMimPg3CanVWqG9mvp3WQMyTb1gKPTnj3hLr-IDCvt9LNoT-fozOgLjT2dRr-wRsBDbzUQf30xAArO9mvp3WQMyTb1gKPTnj3hLtU8e5jZjH61oBY07CTcDGsG5DMsXBio5HMpor9vkDVW9mvp3WQMyTb1gKPTnj3hLuPB42YOiSsQzIWOTiDUUzZMsM68Y591wiEyCNfQnVza9mvp3WQMyTb1gKPTnj3hLuXoIiQWcA1_x1UtttTsRuXZmaNn5VSR8AosoN9egTNm9mvp3WQMyTb1gKPTnj3hLvIemaOgZZkictQjugFGDwZ5qzSTPF3mcoGLS44TaDqe9mvp3WQMyTb1gKPTnj3hLxAm9rEd1rdjbkqoitbcY-4yUoUYsH-mkFrldijOIwvy9mvp3WQMyTb1gKPTnj3hLxhfBqLHuKoEcKLWoG0yD18mLWwwnKB1hAgfr5pLCln-9mvp3WQMyTb1gKPTnj3hLyQ8zZhe45_mDl1QTyZfxC3PrJn_YoQy5472_xmer24u9mvp3WQMyTb1gKPTnj3hLy2uFi0DToJh2WBW1ksFRSklgT6_WCBnaiNenbpd4_ve9mvp3WQMyTb1gKPTnj3hLzjv6vlnWfOisjf1KFvfEPvnCJFE_vGVZV9c1-in1QM69mvp3WQMyTb1gKPTnj3hL2MvrlzX1Zys2fk-WzcdJaWFdFwdK6WxyTULOAhb48_q9mvp3WQMyTb1gKPTnj3hL6Swi6ztWQtZcHsLK8kfSWUc47rt_s4QaRJVvWeKw0fq9mvp3WQMyTb1gKPTnj3hL_d1uPSnqhMd0Pa1KG9vHALX-wbOR-TJAkIasxx3W29i9mvp3WQMyTb1gKPTnj3hL_mOoT3gsydP88sz5_BH70Ddgh4dY0mKF7RJmm9xubQG9mvp3WQMyTb1gKPTnj3hL_s-yMtEumUttSF0scWdyiqVSWYStXKYedRYiHweaFDa9mvp3WQMyTb1gKPTnj3hLyhcdYUqNfhIck5SM0P5V05mB-dEaqW4DRQpBUifCxlu9mvp3WQMyTb1gKPTnj3hLVbmbDeU9vP5IWqnHN88_thbvPZH6tZmqfKsZ7adjtbq9mvp3WQMyTb1gKPTnj3hLd90ZD6MNiP9eOwEaCuYeYgl4DBMLU17Lh-bwiIoLay-9mvp3WQMyTb1gKPTnj3hLyDyxOSKtmfVgdEZ13TfMlNytWh_Lpkcv7jQRcdk56IS9mvp3WQMyTb1gKPTnj3hLOwKHUz4Mw9DsGqgjy_CpQarYchV50cSZgC3Rw6Y2uKm9mvp3WQMyTb1gKPTnj3hLk5ru9PX6UeIzQMPy5JBIzohyUmr991LDp_Oj8ryfYEm9mvp3WQMyTb1gKPTnj3hLZFdb2RJ4mi4UrVb2NB9Sr2v4DPlEAHhZdenwTi1k10W9mvp3WQMyTb1gKPTnj3hLRcfIrnUKz7tI_DdSfWQS3WRNrtiRPM2KJMlNhWln344=",
              "fileType": "BIN"
            }
          ]
        },
        "source": "https://www.googleapis.com/compute/v1/projects/hydra-415522/zones/europe-west9-b/disks/justicons-europe-west9-b-vm",
        "type": "PERSISTENT"
      }
    ],
    "fingerprint": "mhbcTjoNrLw=",
    "id": "5541042680144514285",
    "kind": "compute#instance",
    "labelFingerprint": "54ffHQLiMnU=",
    "labels": {
      "goog-ec-src": "vm_add-gcloud"
    },
    "lastStartTimestamp": "2024-03-05T11:27:04.174-08:00",
    "machineType": "https://www.googleapis.com/compute/v1/projects/hydra-415522/zones/europe-west9-b/machineTypes/e2-medium",
    "metadata": {
      "fingerprint": "JXx8fsmDnc4=",
      "items": [
        {
          "key": "enable-oslogin",
          "value": "true"
        },
        {
          "key": "ssh-keys",
          "value": "justiconsrunner:ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAINFUxJyYOV4crJxJk/UW3gLvCANAD/y1uwDZtmbduKcc daaronch@M1-Max.local\n"
        },
        {
          "key": "user-data",
          "value": "Content-Type: multipart/mixed; boundary=\"MIMEBOUNDARY\"\nMIME-Version: 1.0\r\n\r\n--MIMEBOUNDARY\r\nContent-Disposition: attachment; filename=\"cloud-config.yaml\"\r\nContent-Transfer-Encoding: 7bit\r\nContent-Type: text/cloud-config\r\nMime-Version: 1.0\r\n\r\n#cloud-config\npackages:\n  - git\n  - make\n  - curl\n  - gunicorn\n\nwrite_files:\n  - encoding: b64\n    content: |\n      IyEvYmluL2Jhc2gKIyBzaGVsbGNoZWNrIGRpc2FibGU9U0MxMDkxLFNDMjMxMixTQzIxNTUKc2V0IC1ldW8gcGlwZWZhaWwKSUZTPSQnXG5cdCcKCiMgd2Ugc3RhcnQgd2l0aCBub25lIGFzIHRoZSBkZWZhdWx0ICgibm9uZSIgcHJldmVudHMgdGhlIG5vZGUgY29ubmVjdGluZyB0byBvdXIgZGVmYXVsdCBib290c3RyYXAgbGlzdCkKZXhwb3J0IENPTk5FQ1RfUEVFUj0ibm9uZSIKCiMgU3BlY2lhbCBjYXNlIC0gZ2V0IHRhaWxzY2FsZSBhZGRyZXNzIGlmIGFueQojIElmIHRoZSB0YWlsc2NhbGUwIGFkZHJlc3MgZXhpc3RzIGluIHRoZSBjb21tYW5kIGlwCiMgR2V0IGludGVybmFsIElQIGFkZHJlc3MgZnJvbSB0aGUgZmlyc3QgcmVzdWx0IHRoYXQgc3RhcnRzIHdpdGggMTAuCmV4cG9ydCBJUD0kKGlwIC00IGFkZHIgc2hvdyB8IGdyZXAgLW9QICcoPzw9aW5ldFxzKVxkKyhcLlxkKyl7M30nIHwgZ3JlcCAtRSAnXjEwXC4nIHwgaGVhZCAtbiAxKQoKaWYgW1sgLW4gIiR7SVB9IiBdXTsgdGhlbgogIGV4cG9ydCBCQUNBTEhBVV9QUkVGRVJSRURfQUREUkVTUz0iJHtJUH0iCmZpCgojIGlmIHRoZSBmaWxlIC9ldGMvYmFjYWxoYXUtYm9vdHN0cmFwIGV4aXN0cywgdXNlIGl0IHRvIHBvcHVsYXRlIHRoZSBDT05ORUNUX1BFRVIgdmFyaWFibGUKaWYgW1sgLWYgL2V0Yy9iYWNhbGhhdS1ib290c3RyYXAgXV07IHRoZW4KICAjIHNoZWxsY2hlY2sgZGlzYWJsZT1TQzEwOTAKICBzb3VyY2UgL2V0Yy9iYWNhbGhhdS1ib290c3RyYXAKICBDT05ORUNUX1BFRVI9IiR7QkFDQUxIQVVfTk9ERV9MSUJQMlBfUEVFUkNPTk5FQ1R9IgpmaQoKIyBJZiAvZXRjL2JhY2FsaGF1LW5vZGUtaW5mbyBleGlzdHMsIHRoZW4gbG9hZCB0aGUgdmFyaWFibGVzIGZyb20gaXQKaWYgW1sgLWYgL2V0Yy9iYWNhbGhhdS1ub2RlLWluZm8gXV07IHRoZW4KICAjIHNoZWxsY2hlY2sgZGlzYWJsZT1TQzEwOTAKICAuIC9ldGMvYmFjYWxoYXUtbm9kZS1pbmZvCmZpCgpsYWJlbHM9ImlwPSR7SVB9IgoKIyBJZiBSRUdJT04gaXMgc2V0LCB0aGVuIHdlIGNhbiBhc3N1bWUgYWxsIGxhYmVscyBhcmUgc2V0LCBhbmQgd2Ugc2hvdWxkIGFkZCBpdCB0byB0aGUgbGFiZWxzCmlmIFtbIC1uICIke1JFR0lPTn0iIF1dOyB0aGVuCiAgbGFiZWxzPSIke2xhYmVsc30scmVnaW9uPSR7UkVHSU9OfSx6b25lPSR7Wk9ORX0sYXBwbmFtZT0ke0FQUE5BTUV9IgpmaQoKYmFjYWxoYXUgc2VydmUgXAogIC0tbm9kZS10eXBlIGNvbXB1dGUgXAogIC0tam9iLXNlbGVjdGlvbi1kYXRhLWxvY2FsaXR5IGFueXdoZXJlIFwKICAtLXN3YXJtLXBvcnQgMTIzNSBcCiAgLS1hcGktcG9ydCAxMjM0IFwKICAtLXBlZXIgIiR7Q09OTkVDVF9QRUVSfSIgXAogIC0tcHJpdmF0ZS1pbnRlcm5hbC1pcGZzPXRydWUgXAogIC0tam9iLXNlbGVjdGlvbi1hY2NlcHQtbmV0d29ya2VkIFwKICAtLWxhYmVscyAiJHtsYWJlbHN9Igo=\n    owner: root:root\n    path: /node/start-bacalhau.sh\n    permissions: \"0700\"\n  - encoding: b64\n    content: |\n      W1VuaXRdCkRlc2NyaXB0aW9uPUJhY2FsaGF1IERhZW1vbgpBZnRlcj1uZXR3b3JrLW9ubGluZS50YXJnZXQKV2FudHM9bmV0d29yay1vbmxpbmUudGFyZ2V0IHN5c3RlbWQtbmV0d29ya2Qtd2FpdC1vbmxpbmUuc2VydmljZQoKW1NlcnZpY2VdCkVudmlyb25tZW50PSJMT0dfVFlQRT1qc29uIgpFbnZpcm9ubWVudD0iQkFDQUxIQVVfUEFUSD0vZGF0YSIKRW52aXJvbm1lbnQ9IkJBQ0FMSEFVX0RJUj0vZGF0YSIKUmVzdGFydD1hbHdheXMKUmVzdGFydFNlYz01cwpFeGVjU3RhcnQ9YmFzaCAvbm9kZS9zdGFydC1iYWNhbGhhdS5zaAoKW0luc3RhbGxdCldhbnRlZEJ5PW11bHRpLXVzZXIudGFyZ2V0\n    owner: root:root\n    path: /etc/systemd/system/bacalhau.service\n    permissions: \"0600\"\n  - content: |\n      export PROJECT_ID=hydra-415522\n      export REGION=europe-west9-b\n      export ZONE=europe-west9-b\n      export APPNAME=justicons\n      export SITEURL=justicons.org\n      export TOKEN=8097a91e-bc5d-43db-889b-acd0dee618bc\n    owner: root:root\n    permissions: \"0444\"\n    path: /etc/bacalhau-node-info\n  - encoding: b64\n    content: |\n      IyEvdXNyL2Jpbi9lbnYgYmFzaApzZXQgLWUKc2V0IC14CgpleHBvcnQgRU5WRklMRT0iL2hvbWUvJHtBUFBVU0VSfS8uZW52IgoKc291cmNlICIke0VOVkZJTEV9IgoKYXB0IHVwZGF0ZQphcHQgaW5zdGFsbCAteSBnY2MgbWFrZSBwa2ctY29uZmlnIGxpYnNxbGl0ZTMtZGV2IGxpYmx6bWEtZGV2IGxpYmJ6Mi1kZXYgbGlibmN1cnNlczUtZGV2IGxpYmZmaS1kZXYgbGlicmVhZGxpbmUtZGV2IGxpYnNzbC1kZXYKCmFwdCBpbnN0YWxsIC15IHNvZnR3YXJlLXByb3BlcnRpZXMtY29tbW9uCmFkZC1hcHQtcmVwb3NpdG9yeSAteSBwcGE6ZGVhZHNuYWtlcy9wcGEKYXB0IHVwZGF0ZQphcHQgaW5zdGFsbCAteSBweXRob24zLjExIHB5dGhvbjMuMTEtdmVudiBweXRob24zLjExLWRpc3R1dGlscyBweXRob24zLjExLXRrCnVwZGF0ZS1hbHRlcm5hdGl2ZXMgLS1pbnN0YWxsIC91c3IvYmluL3B5dGhvbiBweXRob24gL3Vzci9iaW4vcHl0aG9uMy4xMSAwCmN1cmwgLXNTIGh0dHBzOi8vYm9vdHN0cmFwLnB5cGEuaW8vZ2V0LXBpcC5weSB8IHN1ZG8gcHl0aG9uMy4xMQoKIyBDbGVhbiB1cCBvbGQgZmlsZXMsIGp1c3QgdG8gYmUgc3VyZQpleHBvcnQgVVNFUkhPTUU9Ii9ob21lLyR7QVBQVVNFUn0iCmV4cG9ydCBQQVRIPSIke1VTRVJIT01FfS8ubG9jYWwvYmluOiR7UEFUSH0iCmV4cG9ydCBTRVRVUFZFTlZTQ1JJUFQ9IiR7VVNFUkhPTUV9L3NldHVwLXZlbnYuc2giCgplY2hvICJVU0VSSE9NRTogJHtVU0VSSE9NRX0iCmVjaG8gIkFQUFVTRVI6ICR7QVBQVVNFUn0iCmVjaG8gIkFQUERJUjogJHtBUFBESVJ9IgplY2hvICJQQVRIOiAke1BBVEh9IgoKZWNobyAiUnVubmluZyBzZXR1cC12ZW52LnNoIC4uLiIKcHVzaGQgJHtBUFBESVJ9CmNob3duIC1SICR7QVBQVVNFUn06JHtBUFBVU0VSfSAke1NFVFVQVkVOVlNDUklQVH0Kc3VkbyAtRSAtdSAke0FQUFVTRVJ9IGJhc2ggLWMgInNvdXJjZSAke0VOVkZJTEV9ICYmICR7U0VUVVBWRU5WU0NSSVBUfSIKcG9wZAoKbWtkaXIgLXAgL2V0Yy9zeXN0ZW1kL3N5c3RlbS9ndW5pY29ybi5zZXJ2aWNlLmQvCmNobW9kIDA3MDAgL2V0Yy9zeXN0ZW1kL3N5c3RlbS9ndW5pY29ybi5zZXJ2aWNlLmQvCgojIEd1bmljb3JuLnNlcnZpY2UKZWNobyAiQ3JlYXRpbmcgZ3VuaWNvcm4gbG9nIGRpcmVjdG9yaWVzLi4uIgpta2RpciAtcCAvdmFyL2xvZy9ndW5pY29ybgpjaG93biAke0FQUFVTRVJ9OiR7QVBQVVNFUn0gL3Zhci9sb2cvZ3VuaWNvcm4KCmVjaG8gIkNyZWF0aW5nIGd1bmljb3JuIHNlcnZpY2UgdW5pdC4uLiIKY2F0IDw8RU9GIHwgdGVlIC9ldGMvc3lzdGVtZC9zeXN0ZW0vZ3VuaWNvcm4uc2VydmljZSA+IC9kZXYvbnVsbApbVW5pdF0KRGVzY3JpcHRpb249Z3VuaWNvcm4gZGFlbW9uCkFmdGVyPW5ldHdvcmsudGFyZ2V0CgpbU2VydmljZV0KUGVybWlzc2lvbnNTdGFydE9ubHk9VHJ1ZQpUeXBlPW5vdGlmeQpVc2VyPSR7QVBQVVNFUn0KR3JvdXA9JHtBUFBVU0VSfQpXb3JraW5nRGlyZWN0b3J5PSR7QVBQRElSfQpFeGVjU3RhcnQ9JHtBUFBESVJ9LyR7UFlFTlZOQU1FfS9iaW4vZ3VuaWNvcm4gXAogICAgICAgICAgLS1hY2Nlc3MtbG9nZmlsZSAvdmFyL2xvZy9ndW5pY29ybi9hY2Nlc3MubG9nIFwKICAgICAgICAgIC0tZXJyb3ItbG9nZmlsZSAvdmFyL2xvZy9ndW5pY29ybi9lcnJvci5sb2cgXAogICAgICAgICAgLS10aW1lb3V0IDEyMCBcCiAgICAgICAgICAtLXdvcmtlcnMgMiBcCiAgICAgICAgICAtLWNoZGlyICR7QVBQRElSfSBcCiAgICAgICAgICAtYiAwLjAuMC4wOjE0MDQxIFwKICAgICAgICAgIC1iIFs6OjFdOjE2ODYxIFwKICAgICAgICAgIHdzZ2k6YXBwCkV4ZWNSZWxvYWQ9L2Jpbi9raWxsIC1zIEhVUCAkTUFJTlBJRApLaWxsTW9kZT1taXhlZApUaW1lb3V0U3RvcFNlYz01ClByaXZhdGVUbXA9dHJ1ZQoKW0luc3RhbGxdCldhbnRlZEJ5PW11bHRpLXVzZXIudGFyZ2V0CkVPRgoKZWNobyAiUmVzdGFydGluZyBndW5pY29ybiBsb2cgcm90YXRlcnMgLi4uIgpjYXQgPDxFT0YgfCB0ZWUgL2V0Yy9sb2dyb3RhdGUuZC9ndW5pY29ybiA+IC9kZXYvbnVsbAovdmFyL2xvZy9ndW5pY29ybi8qLmxvZyB7CglkYWlseQoJbWlzc2luZ29rCglyb3RhdGUgMTQKCWNvbXByZXNzCglub3RpZmVtcHR5CgljcmVhdGUgMDY0MCAke0FQUFVTRVJ9ICR7QVBQVVNFUn0KCXNoYXJlZHNjcmlwdHMKCXBvc3Ryb3RhdGUKCQlzeXN0ZW1jdGwgcmVsb2FkIGd1bmljb3JuCgllbmRzY3JpcHQKfQpFT0YKCmVjaG8gIlJlc3RhcnRpbmcgYWxsIHNlcnZpY2VzIC4uLiAiCnN1ZG8gc3lzdGVtY3RsIGVuYWJsZSBndW5pY29ybi5zZXJ2aWNlCgpzeXN0ZW1jdGwgZGFlbW9uLXJlbG9hZApzeXN0ZW1jdGwgcmVzdGFydCBndW5pY29ybgplY2hvICJEb25lIHdpdGggR3VuaWNvcm4uIgoKZWNobyAiSW5zdGFsbGluZyBsaWdodGh0dHBkIGZvciBoZWFydGJlYXQiCmFwdCBpbnN0YWxsIC15IGxpZ2h0dHBkCnN5c3RlbWN0bCByZXN0YXJ0IGxpZ2h0dHBkCmVjaG8gLW4gIm9rIiB8IHN1ZG8gdGVlIC92YXIvd3d3L2h0bWwvaW5kZXgubGlnaHR0cGQuaHRtbCA+IC9kZXYvbnVsbAoKIyBQaW5nIGl0c2FkYXNoLndvcmsvdXBkYXRlX3NpdGVzIHdpdGggYSBqc29uIG9mIHRoZSBmb3JtIHsic2l0ZSI6ICJzaXRlX25hbWUiLCAiaXAiOiAiaXBfYWRkcmVzcyJ9CmVjaG8gIlBpbmdpbmcgaXRzYWRhc2gud29yay91cGRhdGUgLi4uIgpleHBvcnQgUFJJVkFURUlQPSQoaXAgYWRkciB8IGF3ayAnL2luZXQvICYmIC8xMFwuLyB7c3BsaXQoJDIsIGlwLCAiLyIpOyBwcmludCBpcFsxXX0nKQpjdXJsIC1YIFBPU1QgLUggIkNvbnRlbnQtVHlwZTogYXBwbGljYXRpb24vanNvbiIgLWQgIntcInNpdGVcIjogXCIke1NJVEVVUkx9XCIsIFwiVE9LRU5cIjogXCIke1RPS0VOfVwiLCBcIlNFUlZFUklQXCI6IFwiJHtQUklWQVRFSVB9XCIgIH0iIGh0dHA6Ly9pdHNhZGFzaC53b3JrL3VwZGF0ZQo=\n    owner: root:root\n    path: /node/install-gunicorn-service.sh\n    permissions: \"0700\"\n  - encoding: b64\n    content: |\n      IyEvdXNyL2Jpbi9lbnYgYmFzaApzZXQgLWUKc2V0IC14CgojIEVuc3VyZSBwb2V0cnkgaXMgaW5zdGFsbGVkCnB5dGhvbiAtbSBwaXAgaW5zdGFsbCAtLXVzZXIgcG9ldHJ5CgojIElmICRBUFBESVIgZG9lcyBub3QgZXhpc3QgdGhlbiBjcmVhdGUgaXQKaWYgWyAhIC1kICIkQVBQRElSIiBdOyB0aGVuCiAgICBta2RpciAtcCAiJEFQUERJUiIKZmkKCmNkICIkQVBQRElSIiB8fCBleGl0CgojIElmIHB5cHJvamVjdC50b21sIGlzbid0IHRoZXJlIHRoZW4gY29weSB0aGUgYXBwIGZpbGVzIGZyb20gL3RtcAoKIyBJbnN0YWxsIHBvZXRyeS1wbHVnaW4tZXhwb3J0CnB5dGhvbiAtbSBwaXAgaW5zdGFsbCAtLXVzZXIgcG9ldHJ5LXBsdWdpbi1leHBvcnQKCiMgRXhwb3J0IGRlcGVuZGVuY2llcyB0byByZXF1aXJlbWVudHMudHh0CnB5dGhvbiAtbSBwb2V0cnkgZXhwb3J0IC0td2l0aG91dC1oYXNoZXMgLS1mb3JtYXQ9cmVxdWlyZW1lbnRzLnR4dCA+IHJlcXVpcmVtZW50cy50eHQKCiMgSW5zdGFsbCB2aXJ0dWFsZW52CnB5dGhvbiAtbSBwaXAgaW5zdGFsbCAtLXVzZXIgdmlydHVhbGVudgoKIyBDcmVhdGUgYW5kIGFjdGl2YXRlIHZpcnR1YWwgZW52aXJvbm1lbnQKcHl0aG9uIC1tIHZlbnYgIiR7UFlFTlZOQU1FfSIKc291cmNlICIke1BZRU5WTkFNRX0vYmluL2FjdGl2YXRlIgoKIyBJbnN0YWxsIFB5dGhvbiBkZXBlbmRlbmNpZXMgZnJvbSByZXF1aXJlbWVudHMudHh0CnB5dGhvbiAtbSBwaXAgaW5zdGFsbCAtciByZXF1aXJlbWVudHMudHh0CgojIERlYWN0aXZhdGUgdmlydHVhbCBlbnZpcm9ubWVudApkZWFjdGl2YXRlCg==\n    path: /tmp/rsync/justiconsrunner/setup-venv.sh\n    permissions: \"0700\"\n  - content: |\n      APPUSER=justiconsrunner\n      APPDIR=/home/justiconsrunner/justiconsapp\n      PYENVNAME=justiconsvenv\n      SITEURL=justicons.org\n      TOKEN=8097a91e-bc5d-43db-889b-acd0dee618bc\n    permissions: \"0444\"\n    path: /tmp/rsync/justiconsrunner/.env\n  - encoding: b64\n    content: |\n      ZXhwb3J0IEJBQ0FMSEFVX05PREVfQ0xJRU5UQVBJX0hPU1Q9MTAuMTI4LjAuMgpleHBvcnQgQkFDQUxIQVVfTk9ERV9DTElFTlRBUElfUE9SVD0xMjM0CmV4cG9ydCBCQUNBTEhBVV9OT0RFX05FVFdPUktfVFlQRT1saWJwMnAKZXhwb3J0IEJBQ0FMSEFVX05PREVfTElCUDJQX1BFRVJDT05ORUNUPS9pcDQvMTAuMTI4LjAuMi90Y3AvMTIzNS9wMnAvUW1ROUxXRnNwakJNMWI4d00yWVdkdFF3M3hGNFhVZW1qWml0S3E5cmRleFN5WQpleHBvcnQgQkFDQUxIQVVfTk9ERV9JUEZTX1NXQVJNQUREUkVTU0VTPS9pcDQvMTAuMTI4LjAuMi90Y3AvNDEwMTEvcDJwL1FtUkxoMU5QdjNKc0ZERmszTnlxRFV1NTF3Q21VSzUzazcyc1N1OU5URHRLWUYK\n    owner: root:root\n    path: /etc/bacalhau-bootstrap\n    permissions: \"0400\"\n\npackage_update: true\n\nruncmd:\n  - echo \"Copying the SSH Key to the server\"\n  - |\n    echo -n \"ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAINFUxJyYOV4crJxJk/UW3gLvCANAD/y1uwDZtmbduKcc daaronch@M1-Max.local\" | awk 1 ORS=' ' >> /root/.ssh/authorized_keys\n  - sudo useradd --create-home -r justiconsrunner -s /usr/bin/bash || echo 'User already exists.'\n  #\n  # Make node directory for all scripts\n  #\n  - mkdir -p /node\n  - chmod 0700 /node\n  - mkdir -p /data\n  - chmod 0700 /data\n  #\n  # Install docker\n  #\n  - sudo apt-get install -y ca-certificates curl gnupg lsb-release\n  - sudo mkdir -p /etc/apt/keyrings\n  - |\n    curl -fsSL \"https://download.docker.com/linux/ubuntu/gpg\" | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg\n    echo \"deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable\" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null\n  - sudo apt-get update -y\n  - sudo apt -y install docker-ce docker-ce-cli containerd.io docker-compose-plugin\n  #\n  # Install Bacalhau\n  #\n  - |\n    curl -sL https://get.bacalhau.org/install.sh | BACALHAU_DIR=/$GENHOME/data bash\n  - echo \"Bacalhau downloaded.\"\n  #\n  # Sync from /tmp\n  #\n  - rsync --no-relative /tmp/rsync/justiconsrunner/setup-venv.sh /home/justiconsrunner\n  - rsync --no-relative /tmp/rsync/justiconsrunner/.env /home/justiconsrunner\n  - rm -rf /tmp/rsync\n  #\n  # Install the gunicorn service\n  #\n  - git clone https://github.com/bacalhau-project/examples.git /tmp/web-control-plane\n  - (cd /tmp/web-control-plane && git checkout web-control-plane)\n  - rsync -av --no-relative /tmp/web-control-plane/case-studies/web-control-plane/justicons/client/* /home/justiconsrunner/justiconsapp\n  - chown -R justiconsrunner:justiconsrunner /home/justiconsrunner/justiconsapp\n  - env $(cat /home/justiconsrunner/.env | xargs) /node/install-gunicorn-service.sh\n  -\n  # Reload the systemd daemon, enable, and start the service\n  - sudo sysctl -w net.core.rmem_max=2500000\n  - sudo systemctl daemon-reload\n  - sudo systemctl enable docker\n  - sudo systemctl restart docker\n  - sudo systemctl enable bacalhau.service\n  - sudo systemctl restart bacalhau.service\n  - sleep 20 # Give the log generator a chance to start - and then force generate four entries\n\r\n--MIMEBOUNDARY--\r\n"
        }
      ],
      "kind": "compute#metadata"
    },
    "name": "justicons-europe-west9-b-vm",
    "networkInterfaces": [
      {
        "accessConfigs": [
          {
            "kind": "compute#accessConfig",
            "name": "external-nat",
            "natIP": "34.163.206.194",
            "networkTier": "PREMIUM",
            "type": "ONE_TO_ONE_NAT"
          }
        ],
        "fingerprint": "p2AtFusq0FI=",
        "kind": "compute#networkInterface",
        "name": "nic0",
        "network": "https://www.googleapis.com/compute/v1/projects/hydra-415522/global/networks/global-network",
        "networkIP": "10.200.0.14",
        "stackType": "IPV4_ONLY",
        "subnetwork": "https://www.googleapis.com/compute/v1/projects/hydra-415522/regions/europe-west9/subnetworks/global-network"
      }
    ],
    "scheduling": {
      "automaticRestart": true,
      "onHostMaintenance": "MIGRATE",
      "preemptible": false,
      "provisioningModel": "STANDARD"
    },
    "selfLink": "https://www.googleapis.com/compute/v1/projects/hydra-415522/zones/europe-west9-b/instances/justicons-europe-west9-b-vm",
    "serviceAccounts": [
      {
        "email": "hydra-415522-sa@hydra-415522.iam.gserviceaccount.com",
        "scopes": [
          "https://www.googleapis.com/auth/cloud-platform"
        ]
      }
    ],
    "shieldedInstanceConfig": {
      "enableIntegrityMonitoring": true,
      "enableSecureBoot": false,
      "enableVtpm": true
    },
    "shieldedInstanceIntegrityPolicy": {
      "updateAutoLearnPolicy": true
    },
    "startRestricted": false,
    "status": "RUNNING",
    "tags": {
      "fingerprint": "jqy-0AEP0r0=",
      "items": [
        "allow-bacalhau",
        "allow-ssh",
        "default-allow-internal"
      ]
    },
    "zone": "https://www.googleapis.com/compute/v1/projects/hydra-415522/zones/europe-west9-b"
  }
]"""