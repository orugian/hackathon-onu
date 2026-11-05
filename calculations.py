import math
from domain import DomainError

def _validate_finite_number(value, name, min_val=None, max_val=None, allow_zero=False):
    # Reject booleans (since bool is subclass of int in Python)
    if isinstance(value, bool):
        raise DomainError(f"Campo '{name}' não pode ser booleano.", code="validation_error", status=422)
    if not isinstance(value, (int, float)):
        raise DomainError(f"Campo '{name}' deve ser um número.", code="validation_error", status=422)
    if math.isnan(value) or math.isinf(value):
        raise DomainError(f"Campo '{name}' deve ser um número finito.", code="validation_error", status=422)
    if allow_zero:
        if min_val is not None and value < min_val:
            raise DomainError(f"Campo '{name}' deve ser >= {min_val}.", code="validation_error", status=422)
    else:
        if value <= 0:
            raise DomainError(f"Campo '{name}' deve ser estritamente positivo (> 0).", code="validation_error", status=422)
        if min_val is not None and value < min_val:
            raise DomainError(f"Campo '{name}' deve ser >= {min_val}.", code="validation_error", status=422)
    if max_val is not None and value > max_val:
        raise DomainError(f"Campo '{name}' excede o limite máximo permitido de {max_val}.", code="validation_error", status=422)
    return float(value)

def weigh(volume_m3, gross_kg, tare_kg, density_min=650, density_max=950):
    v = _validate_finite_number(volume_m3, "volume_m3", max_val=1_000_000, allow_zero=False)
    t = _validate_finite_number(tare_kg, "tare_kg", min_val=0, max_val=100_000_000, allow_zero=True)
    g = _validate_finite_number(gross_kg, "gross_kg", max_val=100_000_000, allow_zero=False)
    d_min = _validate_finite_number(density_min, "density_min", allow_zero=False)
    d_max = _validate_finite_number(density_max, "density_max", allow_zero=False)

    if g <= t:
        raise DomainError("Peso bruto deve ser estritamente maior que o peso da tara.", code="validation_error", status=422)
    if d_max < d_min:
        raise DomainError("Densidade máxima deve ser maior ou igual à densidade mínima.", code="validation_error", status=422)

    net_kg = round(g - t, 3)
    net_t = round(net_kg / 1000.0, 4)
    min_kg = round(v * d_min, 3)
    max_kg = round(v * d_max, 3)

    if net_kg < min_kg:
        status = "divergent"
        difference_kg = round(min_kg - net_kg, 3)
    elif net_kg > max_kg:
        status = "divergent"
        difference_kg = round(net_kg - max_kg, 3)
    else:
        status = "compatible"
        difference_kg = 0

    formula = (
        f"net_kg = gross_kg ({g}) - tare_kg ({t}) = {net_kg} kg; "
        f"range = [{v} * {d_min}, {v} * {d_max}] = [{min_kg}, {max_kg}] kg"
    )
    notice = (
        "Faixa hipotética não específica por espécie, não intervalo de confiança; "
        "resultado compatível não comprova legalidade ou ausência de irregularidade."
    )
    return {
        "gross_kg": int(g) if g.is_integer() else g,
        "tare_kg": int(t) if t.is_integer() else t,
        "net_kg": int(net_kg) if net_kg.is_integer() else net_kg,
        "net_t": net_t,
        "min_kg": int(min_kg) if min_kg.is_integer() else min_kg,
        "max_kg": int(max_kg) if max_kg.is_integer() else max_kg,
        "status": status,
        "difference_kg": int(difference_kg) if isinstance(difference_kg, float) and difference_kg.is_integer() else difference_kg,
        "density_min": int(d_min) if d_min.is_integer() else d_min,
        "density_max": int(d_max) if d_max.is_integer() else d_max,
        "formula": formula,
        "notice": notice,
    }

def inventory(diameter_cm, height_m, form_factor):
    dap = _validate_finite_number(diameter_cm, "diameter_cm", min_val=0, max_val=100_000, allow_zero=False)
    h = _validate_finite_number(height_m, "height_m", min_val=0, max_val=100_000, allow_zero=False)
    f = _validate_finite_number(form_factor, "form_factor", min_val=0, max_val=1.0, allow_zero=False)

    if f <= 0 or f > 1.0:
        raise DomainError("Fator de forma f deve satisfazer 0 < f <= 1.", code="validation_error", status=422)

    # Fórmula: pi * (dap/100)^2 * H * f / 4
    radius_m = (dap / 100.0) / 2.0
    area_m2 = math.pi * (radius_m ** 2)
    volume_m3 = round(area_m2 * h * f, 4)

    min_density = 650.0
    max_density = 950.0
    min_mass_t = round(volume_m3 * min_density / 1000.0, 4)
    max_mass_t = round(volume_m3 * max_density / 1000.0, 4)

    formula = f"volume_m3 = pi*(dap/100)^2*H*f/4 = pi*({dap}/100)^2*{h}*{f}/4 = {volume_m3} m³"
    notice = (
        "Estimativa volumétrica baseada em inventário geométrico hipotético; "
        "não modifica crédito florestal e não possui validade oficial de desdobro."
    )

    return {
        "volume_m3": volume_m3,
        "min_mass_t": min_mass_t,
        "max_mass_t": max_mass_t,
        "formula": formula,
        "notice": notice,
    }

