
'''
NIST SP 800-122 does not fix a level per data type (the level depends on
identifiability, field sensitivity, context of use, ...), so this is a default
derived from two of its factors:
  HIGH     fields NIST calls generally more sensitive (SSN, financial account,
           medical) and government-issued IDs
  MODERATE directly identifying fields (name, email, phone)
  LOW      indirectly identifying / linkable data (location, IP, MAC)


'''
from ..findings import Tier

PII_ENTITY_TIER: dict[str, Tier] = {
    # HIGH
    "CREDIT_CARD": Tier.PII_HIGH,
    "IBAN_CODE": Tier.PII_HIGH,
    "NRP": Tier.PII_HIGH,
    "US_BANK_NUMBER": Tier.PII_HIGH,
    "US_DRIVER_LICENSE": Tier.PII_HIGH,
    "US_ITIN": Tier.PII_HIGH,
    "US_HEALTH_INSURANCE_MEMBER_ID": Tier.PII_HIGH,
    "US_MBI": Tier.PII_HIGH,
    "US_PASSPORT": Tier.PII_HIGH,
    "US_SSN": Tier.PII_HIGH,
    "UK_DRIVING_LICENCE": Tier.PII_HIGH,
    "UK_NHS": Tier.PII_HIGH,
    "UK_NINO": Tier.PII_HIGH,
    "UK_PASSPORT": Tier.PII_HIGH,
    "ES_NIF": Tier.PII_HIGH,
    "ES_NIE": Tier.PII_HIGH,
    "ES_PASSPORT": Tier.PII_HIGH,
    "IT_FISCAL_CODE": Tier.PII_HIGH,
    "IT_DRIVER_LICENSE": Tier.PII_HIGH,
    "IT_PASSPORT": Tier.PII_HIGH,
    "IT_IDENTITY_CARD": Tier.PII_HIGH,

    "PL_PESEL": Tier.PII_HIGH,

    "SG_NRIC_FIN": Tier.PII_HIGH,

    "AU_TFN": Tier.PII_HIGH,
    "AU_MEDICARE": Tier.PII_HIGH,

    "IN_PAN": Tier.PII_HIGH,
    "IN_AADHAAR": Tier.PII_HIGH,
    "IN_VOTER": Tier.PII_HIGH,
    "IN_PASSPORT": Tier.PII_HIGH,

    "FI_PERSONAL_IDENTITY_CODE": Tier.PII_HIGH,

    "KR_DRIVER_LICENSE": Tier.PII_HIGH,
    "KR_FRN": Tier.PII_HIGH,
    "KR_PASSPORT": Tier.PII_HIGH,
    "KR_RRN": Tier.PII_HIGH,

    "NG_NIN": Tier.PII_HIGH,

    "PH_PASSPORT": Tier.PII_HIGH,
    "PH_TIN": Tier.PII_HIGH,

    "CA_SIN": Tier.PII_HIGH,
    "SE_PERSONNUMMER": Tier.PII_HIGH,

    "ZA_ID_NUMBER": Tier.PII_HIGH,
    "ZA_PASSPORT": Tier.PII_HIGH,
    "ZA_INCOME_TAX_NUMBER": Tier.PII_HIGH,
    "ZA_DRIVER_LICENSE": Tier.PII_HIGH,

    "TH_TNIN": Tier.PII_HIGH,
    "TR_NATIONAL_ID": Tier.PII_HIGH,
    "PH_UMID": Tier.PII_HIGH,

    "DE_TAX_ID": Tier.PII_HIGH,
    "DE_TAX_NUMBER": Tier.PII_HIGH,
    "DE_PASSPORT": Tier.PII_HIGH,
    "DE_ID_CARD": Tier.PII_HIGH,
    "DE_SOCIAL_SECURITY": Tier.PII_HIGH,
    "DE_HEALTH_INSURANCE": Tier.PII_HIGH,

    "MEDICAL_DISEASE_DISORDER": Tier.PII_HIGH,
    "MEDICAL_MEDICATION": Tier.PII_HIGH,
    "MEDICAL_THERAPEUTIC_PROCEDURE": Tier.PII_HIGH,
    "MEDICAL_BIOLOGICAL_ATTRIBUTE": Tier.PII_HIGH,
    "MEDICAL_FAMILY_HISTORY": Tier.PII_HIGH,
    "MEDICAL_HISTORY": Tier.PII_HIGH,



    # MODERATE
    "EMAIL_ADDRESS": Tier.PII_MODERATE,
    "PERSON": Tier.PII_MODERATE,
    "PHONE_NUMBER": Tier.PII_MODERATE,
    "MEDICAL_LICENSE": Tier.PII_MODERATE,
    "US_CLAIM_NUMBER": Tier.PII_MODERATE,
    "US_PRESCRIPTION_NUMBER": Tier.PII_MODERATE,
    "US_PRIOR_AUTHORIZATION_NUMBER": Tier.PII_MODERATE,
    "US_REFERRAL_NUMBER": Tier.PII_MODERATE,
    "ZA_TRAFFIC_REGISTER_NUMBER": Tier.PII_MODERATE,
    "ZA_MOBILE_NUMBER": Tier.PII_MODERATE,
    "ZA_TELEPHONE_NUMBER": Tier.PII_MODERATE,

    "MEDICAL_CLINICAL_EVENT": Tier.PII_MODERATE,



    # LOW
    "IP_ADDRESS": Tier.PII_LOW,
    "MAC_ADDRESS": Tier.PII_LOW, # not in every Presidio version: skipped with a warning if missing
    "LOCATION": Tier.PII_LOW,
    "US_NPI": Tier.PII_LOW,
    "US_PROVIDER_TAX_ID": Tier.PII_LOW,
    "UK_POSTCODE": Tier.PII_LOW,
    "UK_VEHICLE_REGISTRATION": Tier.PII_LOW,

    "IT_VAT_CODE": Tier.PII_LOW,
    "SG_UEN": Tier.PII_LOW,
    "AU_ABN": Tier.PII_LOW,
    "AU_ACN": Tier.PII_LOW,

    "IN_VEHICLE_REGISTRATION": Tier.PII_LOW,
    "IN_GSTIN": Tier.PII_LOW,

    "KR_BRN": Tier.PII_LOW,

    "NG_VEHICLE_REGISTRATION": Tier.PII_LOW,

    "CA_POSTAL_CODE": Tier.PII_LOW,
    "SE_ORGANISATIONSNUMMER": Tier.PII_LOW,
    "ZA_VAT_NUMBER": Tier.PII_LOW,
    "ZA_COMPANY_REGISTRATION": Tier.PII_LOW,
    "ZA_LICENSE_PLATE": Tier.PII_LOW,
    "TR_LICENSE_PLATE": Tier.PII_LOW,

    "DE_KFZ": Tier.PII_LOW,
    "DE_HANDELSREGISTER": Tier.PII_LOW,
    "DE_PLZ": Tier.PII_LOW,


    # deliberately NOT enabled: DATE_TIME, URL, AGE, ORGANIZATION, CRYPTO.
    # they fire constantly on ordinary code and are not PII by themselves.
}


'''
# PII Risk Tier Classification

LakanVault maps Presidio entity types to three PII risk tiers, based on the confidentiality impact levels described in **NIST SP 800-122, Section 3**.

The classifications are project-level defaults informed by NIST's risk-based approach.

| Tier | Description | Examples |
|---|---|---|
| **PII_HIGH** | Sensitive identifiers or personal information that could lead to identity theft, financial fraud, or significant privacy harm. | SSN, passport, bank account, medical history |
| **PII_MODERATE** | Personal information that identifies or enables contact with an individual but generally has a lower disclosure impact. | Person name, email, phone number |
| **PII_LOW** | Information that provides limited identification on its own but may contribute to identifying or tracking someone when combined with other data. | Location, IP address, MAC address, business identifiers |

## Classification Rules

- **Government-issued personal identifiers:** Generally HIGH due to their persistent nature and connection to government or administrative records.
- **Financial identifiers:** HIGH due to potential financial fraud and unauthorised access.
- **Healthcare information:** HIGH when it reveals an individual's medical conditions, treatment, or history.
- **Contact information:** MODERATE because it can enable targeted contact and social engineering.
- **Geographic and technical identifiers:** LOW because they generally require additional information to identify an individual.
- **Business identifiers:** Generally LOW because they primarily identify organisations rather than individuals.

Entities that are not inherently PII, such as `DATE_TIME`, `URL`, and `UUID`, are excluded unless their context establishes a privacy risk.

**Note:** These are default project-level classifications, not fixed classifications prescribed by NIST. Detection confidence and risk tier are treated as separate values.

**Reference:** NIST SP 800-122 (2010), *Guide to Protecting the Confidentiality of Personally Identifiable Information (PII)*, Section 3.
'''