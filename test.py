from common.transcriber import transcribe_from_blob_url
from common.summarizer import summarize_transcript
blob_url = "https://metameetingtoolstorage.blob.core.windows.net/meetings/81711554935/mp4_d529d34b-ca52-4418-9827-07463c1afe50.mp4"  # Replace with actual Blob URL
transcript = transcribe_from_blob_url(blob_url)
print(transcript)
transcript = """
John: Let's finalize the product launch for next Tuesday.
Sara: I'll prepare the press release.
Mike: I’ll check with dev team for final QA testing.
"""

summary = summarize_transcript(transcript)
print(summary)

