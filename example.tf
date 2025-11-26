data "google_project" "project" {}

resource "google_kms_crypto_key_iam_member" "kms-secret-binding" {
  crypto_key_id = "kms-key"
  role          = "roles/cloudkms.cryptoKeyEncrypterDecrypter"
  member        = "serviceAccount:service-${data.google_project.project.number}@gcp-sa-secretmanager.iam.gserviceaccount.com"
}

resource "google_secret_manager_secret" "secret-with-automatic-cmek" {
  secret_id = "secret"

  replication {
    auto {
      customer_managed_encryption {
        kms_key_name = "kms-key"
      }
    }
  }

  depends_on = [ google_kms_crypto_key_iam_member.kms-secret-binding ]
}