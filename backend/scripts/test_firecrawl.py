import sys
import json
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from services.verification_service import search_and_scrape_evidence
import services.verification_service as vs

vs.FIRECRAWL_API_KEY = os.getenv("FIRECRAWL_API_KEY")

claim = "The government has initiated the demolition of illegally constructed buildings along riverbanks as part of its campaign to clear squatter settlements. This action, affecting some buildings used for commercial activities, is currently a subject of public discussion."

res = search_and_scrape_evidence(claim, use_firecrawl=True)
print("Result:")
print(json.dumps(res, indent=2))
