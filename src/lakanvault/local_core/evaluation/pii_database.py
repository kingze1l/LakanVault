
'''
reminder note: this is what you are going to do next
just copy the same format as the secret database, and then instead of using
df = pd.read_parquet("hf://datasets/Podric/prowl-secrets-corpus/corpus.parquet"), use the PII benchmark link 

make sure that it is all positive samples
in PII probably match the value and also the enitity type
result would probably be something like
matched: TRUE/FALSE : if it manage to find the correct span of PII
entity_matched: TRUE/FALSE : if it manage to find the correct entity 
in a scenario where LakanVault find multiple entity, biut there are only one entity, do a loop of found entity and match the truth entity, if it found it then matched is true
check entity_matched if it the same and retrun tryue as well

data would look something like
[Finding, Finding]
[(text, start, end, entity_type), (), ...]

class Finding:
    entity_type: str               # e.g. "aws-access-token", "EMAIL_ADDRESS"
    text: str = field(repr=False)  # matched value (repr=False: never leak in logs)
    start: int                     # character offset in the prompt (inclusive)
    end: int                       # character offset (exclusive)
    confidence: float              # 0..1
    tier: Tier
    source: str                    # "secrets" | "presidio" | ... (LLM layer adds "llm")

potential dataset : 
- https://huggingface.co/datasets/Pritesh-2711/pii-bench doesnt seem to have enittiy type here

monday, tuesday finishing benchmark
thursday opaque sanitization
friday website 
'''