import math
from app.models.enums import ServiceType
from app.schemas.parcel import ParcelQuoteResponse


class PricingEngine:
    BASE_CHARGE = 50.0  # Base shipment booking charge
    RATE_PER_KG = 25.0  # Charge per kg
    DIM_DIVISOR = 5000.0  # IATA volumetric divisor (L * W * H / 5000)
    TAX_RATE = 0.18  # 18% GST

    SERVICE_MULTIPLIERS = {
        ServiceType.STANDARD: (1.0, 4),
        ServiceType.EXPRESS: (1.4, 2),
        ServiceType.OVERNIGHT: (1.8, 1),
        ServiceType.SAME_DAY: (2.5, 1),
    }

    @classmethod
    def calculate_quote(
        cls,
        weight_kg: float,
        length_cm: float,
        width_cm: float,
        height_cm: float,
        service_type: ServiceType = ServiceType.STANDARD
    ) -> ParcelQuoteResponse:
        # Calculate volumetric weight
        volumetric_weight = round((length_cm * width_cm * height_cm) / cls.DIM_DIVISOR, 2)
        chargeable_weight = max(weight_kg, volumetric_weight)

        multiplier, estimated_days = cls.SERVICE_MULTIPLIERS.get(service_type, (1.0, 4))

        base_charge = cls.BASE_CHARGE
        weight_charge = round(chargeable_weight * cls.RATE_PER_KG, 2)
        subtotal = (base_charge + weight_charge) * multiplier
        service_charge = round(subtotal - (base_charge + weight_charge), 2)
        
        tax_amount = round(subtotal * cls.TAX_RATE, 2)
        total_charge = round(subtotal + tax_amount, 2)

        return ParcelQuoteResponse(
            weight_kg=weight_kg,
            volumetric_weight_kg=volumetric_weight,
            chargeable_weight_kg=chargeable_weight,
            base_charge=base_charge,
            weight_charge=weight_charge,
            service_charge=service_charge,
            tax_amount=tax_amount,
            total_charge=total_charge,
            estimated_delivery_days=estimated_days
        )

