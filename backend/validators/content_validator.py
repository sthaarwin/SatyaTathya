import re
from typing import Tuple
import logging

logger = logging.getLogger(__name__)


class ContentValidator:
    """Validates and enhances content quality"""

    NEPALI_CHAR_RANGE = (0x0900, 0x097F)  # Unicode range for Devanagari (Nepali)
    
    @staticmethod
    def validate_claim_extractability(claim: str) -> Tuple[bool, float]:
        """
        Check if claim is well-formed and extractable.
        Returns (is_valid, confidence_score)
        """
        if not claim or len(claim.strip()) < 5:
            return False, 0.0
        
        claim = claim.strip()
        
        # Heuristics for quality
        words = claim.split()
        has_min_length = len(words) >= 3
        
        # Check for subject-verb structure (English + Nepali)
        has_verb = any(
            word.lower() in {
                # English verbs
                'is', 'are', 'was', 'were', 'be', 'been', 'being',
                'has', 'have', 'had', 'do', 'does', 'did',
                'will', 'would', 'shall', 'should', 'can', 'could', 'may', 'might',
                'said', 'claims', 'claimed', 'reported', 'announced', 'stated',
                'suggests', 'suggested', 'shows', 'showed', 'proves', 'proved',
                'indicates', 'indicated', 'causes', 'caused', 'happens', 'happened',
                'occurs', 'occurred', 'confirmed', 'denied', 'revealed', 'disclosed',
                'declared', 'mentioned', 'noted', 'added', 'explained', 'responded',
                'acknowledged', 'admitted', 'warned', 'urged', 'called', 'demanded',
                'proposed', 'opposed', 'supported', 'criticized', 'accused', 'praised',
                'ordered', 'banned', 'approved', 'rejected', 'launched', 'started',
                'completed', 'opened', 'signed', 'passed', 'implemented', 'published',
                'issued', 'allocated', 'inaugurated', 'resumed', 'stopped', 'cancelled',
                'filed', 'submitted', 'recommended', 'directed', 'instructed',
                # Nepali verbs (common forms)
                'भन्छन्', 'भनिन्', 'भने', 'भन्यो', 'भन्नुभयो',
                'छन्', 'छिन्', 'छ', 'थिए', 'थिइन्', 'थियो', 'थिई',
                'हो', 'हुन्', 'हौ', 'हुँ',
                'गरे', 'गर्छ', 'गर्छन्', 'गरिन्', 'गर्यो', 'गरिन', 'गर्नुभयो',
                'भएको', 'भए', 'भयो', 'भइन्',
                'दिए', 'दिन्छ', 'दियो', 'दिइन्',
                'लिए', 'लिन्छ', 'लियो', 'लिइन्',
                'पुगे', 'पुग्यो', 'पुगिन्',
                'आए', 'आयो', 'आइन्', 'आउँछ', 'आउँछन्',
                'गए', 'गयो', 'गइन्', 'जान्छ', 'जान्छन्',
                'बने', 'बन्यो', 'बनिन्', 'बन्छ',
                'रहे', 'रह्यो', 'रहेको', 'रहेछ',
                'उल्लेख', 'जनाए', 'बताए', 'बताइन्',
                'अनुसार', 'प्रकाशित', 'घोषणा',
                'ठहर', 'ठहर्यो', 'फैसला', 'आदेश',
                'स्वीकार', 'अस्वीकार', 'खारेज', 'पारित',
            }
            for word in words
        )
        
        # Check for question marks or incomplete statements
        is_incomplete = claim.endswith(('?', '...', 'what', 'how', 'why'))
        
        # Calculate confidence
        confidence = 0.0
        if has_min_length:
            confidence += 0.4
        if has_verb:
            confidence += 0.4
        if not is_incomplete:
            confidence += 0.2
        
        is_valid = has_min_length and has_verb and not is_incomplete
        
        return is_valid, min(1.0, confidence)

    @staticmethod
    def detect_language(text: str) -> str:
        """
        Detect language: 'nepali', 'english', 'mixed', or 'unknown'
        """
        if not text:
            return "unknown"
        
        nepali_count = sum(
            1 for char in text 
            if ContentValidator.NEPALI_CHAR_RANGE[0] <= ord(char) <= ContentValidator.NEPALI_CHAR_RANGE[1]
        )
        
        total_chars = len(text)
        nepali_ratio = nepali_count / total_chars if total_chars > 0 else 0
        
        if nepali_ratio > 0.5:
            return "nepali"
        elif nepali_ratio > 0.1:
            return "mixed"
        else:
            # Simple heuristic for English
            if any(word in text.lower() for word in ['the', 'is', 'and', 'to', 'of']):
                return "english"
            return "unknown"

    @staticmethod
    def fix_transcription_errors(text: str) -> str:
        """
        Fix common speech-to-text errors and normalize text.
        Common fixes for Nepali/English code-switching.
        """
        if not text:
            return text
        
        # Fix common misrecognitions
        corrections = {
            r'\bnepal\b': 'Nepal',
            r'\bkathmandu\b': 'Kathmandu',
            r'\bpokhara\b': 'Pokhara',
            r'\bdhaka\b': 'Dhaka',
            r'\bbangladesh\b': 'Bangladesh',
            r'\bindia\b': 'India',
            r'\bchina\b': 'China',
            r'\bnepalese\b': 'Nepali',
            r'\bprime\s+minister\b': 'Prime Minister',
            r'\bgovernment\b': 'government',
            r'  +': ' ',  # Multiple spaces to single
        }
        
        result = text
        for pattern, replacement in corrections.items():
            result = re.sub(pattern, replacement, result, flags=re.IGNORECASE)
        
        # Trim whitespace
        result = result.strip()
        
        return result

    @staticmethod
    def calculate_claim_quality_score(
        claim: str,
        is_extractable: bool,
        language: str,
        confidence: float
    ) -> float:
        """Calculate overall claim quality score (0.0-1.0)"""
        score = 0.0
        
        if is_extractable:
            score += 0.5
        else:
            return 0.0
        
        if language in ['nepali', 'english', 'mixed']:
            score += 0.2
        else:
            score += 0.05
        
        score += confidence * 0.3
        
        return min(1.0, max(0.0, score))

    @staticmethod
    def sanitize_query(query: str) -> str:
        """Sanitize search query"""
        if not query:
            return ""
        
        # Remove excessive special characters
        query = re.sub(r'[^a-zA-Z0-9\s\'\"-]', '', query)
        # Remove extra spaces
        query = re.sub(r'\s+', ' ', query)
        # Trim
        query = query.strip()
        
        return query

    @staticmethod
    def validate_url(url: str) -> Tuple[bool, str]:
        """
        Validate URL format and extractability.
        Returns (is_valid, domain)
        """
        if not url or len(url.strip()) < 10:
            return False, ""
        
        # Simple URL regex
        url_pattern = r'https?://[^\s/$.?#].[^\s]*'
        if not re.match(url_pattern, url):
            return False, ""
        
        # Extract domain
        try:
            domain_match = re.search(r'https?://(?:www\.)?([^/]+)', url)
            domain = domain_match.group(1) if domain_match else ""
            
            allowed_domains = ['tiktok.com', 'youtube.com', 'youtu.be', 'instagram.com']
            is_allowed = any(allowed in domain.lower() for allowed in allowed_domains)
            
            return is_allowed, domain
        except Exception as e:
            logger.error(f"URL validation error: {e}")
            return False, ""
