import enum

class PricingMethod(str, enum.Enum):
    STANDARD = "STANDARD"
    LINE_DISCOUNT = "LINE_DISCOUNT"
    TIERED = "TIERED"
    BLOCK = "BLOCK"
    
    # Future pricing methods defined for extensible design (not implemented yet)
    COST_PLUS_MARKUP = "COST_PLUS_MARKUP"

class TieredMode(str, enum.Enum):
    VOLUME = "VOLUME"
    CUMULATIVE = "CUMULATIVE"
