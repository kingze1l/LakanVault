KEYWORDS = {
    "sc_",      # Authress (start of the key)
    "ext_",     # Authress
    "pat",      # Airtable personal access token (start of the key)
    "b_",       # Beamer API token (start of the key)
    "sl.",      # Dropbox short-lived token (start of the key)

    # 1Password
    "A3-",                 # short, but only used on known secrets so OK
    "ops_eyJ",
    # Adobe
    "p8e-",
    # Age
    "AGE-SECRET-KEY-1",
    # Alibaba
    "LTAI",
    # Anthropic
    "sk-ant-admin01-",
    "sk-ant-api03-",
    # Artifactory
    "AKCp",
    "cmVmd",
    # Atlassian
    "ATATT3",
    # Authress
    "scauth_",
    "authress_",
    # AWS
    "A3T", "AKIA", "ASIA", "ABIA", "ACCA",
    "ABSK",                # Bedrock long-lived key
    "bedrock-api-key-YmVkcm9jay5hbWF6b25hd3MuY29t",
    # Azure
    "Q~",                  # sits in the middle of the secret, find() handles it
    # ClickHouse
    "4b1d",
    # Clojars
    "CLOJARS_", "clojars_",
    # Cloudflare
    "v1.0-",
    # Databricks
    "dapi",
    # Defined Networking
    "dnkey-",
    # DigitalOcean
    "doo_v1_", "dop_v1_", "dor_v1_",
    # Doppler
    "dp.pt.",
    # Dropbox (long-lived token has 10 A's in the middle)
    "AAAAAAAAAA",
    # Duffel
    "duffel_test_", "duffel_live_",
    # Dynatrace
    "dt0c01.",
    # EasyPost
    "EZAK", "EZTK",

    # Facebook page access token
    "eaam",
    "eaac",
    # Flutterwave
    "flwseck_test-",
    "flwpubk_test-",
    # Fly.io
    "fo1_",
    "fm1a_",
    "fm1r_",
    "fm2_",
    # Frame.io
    "fio-u-",
    # Freemius
    "sk_",              # short, but longer ones like sk_live_ win first
    # GCP
    "aiza",

    # GitHub
    "ghu_", "ghs_", "gho_", "ghp_", "ghr_",
    "github_pat_",
    # GitLab
    "glcbt-", "gldt-", "glffct-", "glft-", "glimt-",
    "glagent-", "gloas-", "glpat-", "glptt-",
    "gr1348941",
    "glrt-",                 # also covers the routable version
    "glsoat-",
    "_gitlab_session=",
    # GoCardless / Lob
    "live_", "test_",        # short, but longer ones like sk_live_ win first
    "live_pub_", "test_pub_",
    # Grafana
    "eyjrijoi",
    "glc_",
    "glsa_",
    # Harness
    "pat.", "sat.",
    # HashiCorp Terraform
    "atlasv1",               # sits in the middle of the token
    # Heroku
    "hrku-aa",
    # Hugging Face
    "hf_", "api_org_",
    # Infracost
    "ico-",
    # Intra42
    "s-s4t2ud-", "s-s4t2af-",
    # JWT
    "ey",                    # very short, see note below
    "zxlk",                  # base64-encoded JWT
    # Linear
    "lin_api_",

        # MaxMind (the keyword is at the END of the key, find() handles that)
    "_mmk",
    # Mailgun
    "key-", "pubkey-",
    # New Relic
    "nrjs-", "nrii-", "nrak-",
    # Notion / npm
    "ntn_", "npm_",
    # OpenAI (see note below)
    "sk-", "sk-proj-", "sk-svcacct-", "sk-admin-",
    # OpenShift
    "sha256~",
    # Perplexity
    "pplx-",
    # Plaid
    "access-sandbox-", "access-development-", "access-production-",
    # PlanetScale
    "pscale_tkn_", "pscale_oauth_", "pscale_pw_",
    # Postman / Prefect / Pulumi
    "pmak-", "pnu_", "pul-",
    # Private keys (PEM headers)
    "-----begin private key-----",
    "-----begin rsa private key-----",
    "-----begin ec private key-----",
    "-----begin dsa private key-----",
    "-----begin openssh private key-----",
    "-----begin encrypted private key-----",
    "-----begin pgp private key block-----",
    # PyPI
    "pypi-ageichlwas5vcmc",
    # Readme / RubyGems / Scalingo
    "rdme_", "rubygems_", "tk-us-",
    # SendGrid / Sendinblue
    "sg.", "xkeysib-",
    # Sentry
    "sntrys_", "sntryu_",
    # Settlemint
    "sm_aat_", "sm_pat_", "sm_sat_",
    # Shippo
    "shippo_live_", "shippo_test_",
    # Shopify
    "shpat_", "shpca_", "shppa_", "shpss_",
    # Slack
    "xapp-", "xoxb-", "xoxp-", "xoxe-", "xoxa-", "xoxr-", "xoxo-", "xoxs-",
    "xoxe.xoxb-", "xoxe.xoxp-",
    "https://hooks.slack.com/services/",
    "https://hooks.slack.com/workflows/",
    "https://hooks.slack.com/triggers/",
    "hooks.slack.com/services/",
    # Microsoft Teams webhook
    ".webhook.office.com/webhookb2/",
    # SonarQube
    "squ_", "sqp_", "sqa_",
    # Sourcegraph
    "sgp_",
    # Short ones, only used when nothing longer matches
    "api-",        # Octopus Deploy
    "pk.",         # Mapbox
    # Square
    "sq0atp-",
    "eaaa",
    # Stripe (Gitleaks leaves out the last "_", the real keys have it)
    "sk_test_", "sk_live_", "sk_prod_",
    "rk_test_", "rk_live_", "rk_prod_",
    # Twilio
    "sk",                      # very short, see note below
    # Twitter bearer token (starts with 22 letter A's)
    "aaaaaaaaaaaaaaaaaaaaaa",
    # Typeform
    "tfp_",
    # HashiCorp Vault
    "hvb.", "hvs.", "s.",
    # Yandex
    "t1.", "aqvn",
}