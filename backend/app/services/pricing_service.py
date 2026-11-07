from decimal import Decimal, ROUND_HALF_UP
import math
from typing import Tuple
from app.models.enums import ServiceType
from app.schemas.parcel import ParcelQuoteResponse


class PricingEngine:
    """
    LogiFlows Pricing and Quotation Engine.
    
    Formula Specification:
    1. Volumetric Weight (kg):
       volumetric_weight = (length_cm * width_cm * height_cm) / 5000.0
       (IATA volumetric cubic divisor).
    2. Chargeable Weight (kg):
       chargeable_weight = max(actual_weight_kg, volumetric_weight_kg)
    3. Base Booking Charge:
       base_charge = ₹50.00
    4. Weight Charge:
       weight_charge = chargeable_weight * ₹25.00 per kg
    5. Service Multiplier & SLA:
       - STANDARD:  multiplier = 1.0 (Estimated SLA: 4 days)
       - EXPRESS:   multiplier = 1.4 (Estimated SLA: 2 days)
       - OVERNIGHT: multiplier = 1.8 (Estimated SLA: 1 day)
       - SAME_DAY:  multiplier = 2.5 (Estimated SLA: 1 day)
    6. Subtotal:
       subtotal = (base_charge + weight_charge) * multiplier
    7. Service Surcharge:
       service_charge = subtotal - (base_charge + weight_charge)
    8. Goods & Services Tax (GST 18%):
       tax_amount = subtotal * 0.18
    9. Final Total Payable:
       total_charge = subtotal + tax_amount

    All monetary and weight operations are computed with Decimal arithmetic
    and quantized to two decimal places using ROUND_HALF_UP.
    """

    BASE_CHARGE = Decimal("50.00")
    RATE_PER_KG = Decimal("25.00")
    DIM_DIVISOR = Decimal("5000.0")
    TAX_RATE = Decimal("0.18")

    SERVICE_MULTIPLIERS = {
        ServiceType.STANDARD: (Decimal("1.0"), 4),
        ServiceType.EXPRESS: (Decimal("1.4"), 2),
        ServiceType.OVERNIGHT: (Decimal("1.8"), 1),
        ServiceType.SAME_DAY: (Decimal("2.5"), 1),
    }

    @classmethod
    def round_currency(cls, value: Decimal) -> Decimal:
        return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    @classmethod
    def calculate_quote(
        cls,
        weight_kg: float,
        length_cm: float,
        width_cm: float,
        height_cm: float,
        service_type: ServiceType = ServiceType.STANDARD
    ) -> ParcelQuoteResponse:
        # Validate against NaN and Inf
        for name, val in [("weight_kg", weight_kg), ("length_cm", length_cm), ("width_cm", width_cm), ("height_cm", height_cm)]:
            if math.isnan(val) or math.isinf(val) or val <= 0:
                raise ValueError(f"{name} must be a positive finite number")

        d_weight = Decimal(str(weight_kg))
        d_length = Decimal(str(length_cm))
        d_width = Decimal(str(width_cm))
        d_height = Decimal(str(height_cm))

        # 1. Volumetric weight
        volumetric_weight = cls.round_currency((d_length * d_width * d_height) / cls.DIM_DIVISOR)
        # 2. Chargeable weight
        chargeable_weight = max(d_weight, volumetric_weight)

        multiplier, estimated_days = cls.SERVICE_MULTIPLIERS.get(service_type, (Decimal("1.0"), 4))

        # 3. Base charge
        base_charge = cls.BASE_CHARGE
        # 4. Weight charge
        weight_charge = cls.round_currency(chargeable_weight * cls.RATE_PER_KG)
        raw_base_and_weight = base_charge + weight_charge

        # 5. Subtotal with service multiplier
        subtotal = cls.round_currency(raw_base_and_weight * multiplier)
        service_charge = cls.round_currency(subtotal - raw_base_and_weight)

        # 6. Tax (18% GST)
        tax_amount = cls.round_currency(subtotal * cls.TAX_RATE)
        # 7. Total charge
        total_charge = cls.round_currency(subtotal + tax_amount)

        return ParcelQuoteResponse(
            weight_kg=float(d_weight),
            volumetric_weight_kg=float(volumetric_weight),
            chargeable_weight_kg=float(chargeable_weight),
            base_charge=float(base_charge),
            weight_charge=float(weight_charge),
            service_charge=float(service_charge),
            tax_amount=float(tax_amount),
            total_charge=float(total_charge),
            estimated_delivery_days=estimated_days
        )
