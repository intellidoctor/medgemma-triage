"""Tests for the UI mock service layer."""

from src.agents.triage import PatientData, TriageColor, TriageResult, VitalSigns
from src.ui.mock_services import (
    SAMPLE_CASES,
    build_mock_fhir_bundle,
    mock_analyze_image,
    mock_classify,
)

# ---------------------------------------------------------------------------
# mock_classify
# ---------------------------------------------------------------------------


class TestMockClassify:
    def test_returns_triage_result(self) -> None:
        patient = PatientData(chief_complaint="Dor de cabeça leve")
        result = mock_classify(patient)
        assert isinstance(result, TriageResult)

    def test_chest_pain_orange(self) -> None:
        patient = PatientData(
            chief_complaint="Dor no peito irradiando para braço esquerdo",
            pain_scale=9,
        )
        result = mock_classify(patient)
        assert result.triage_color == TriageColor.ORANGE

    def test_prescription_refill_blue(self) -> None:
        patient = PatientData(
            chief_complaint="Preciso renovar receita de losartana",
            pain_scale=0,
        )
        result = mock_classify(patient)
        assert result.triage_color == TriageColor.BLUE

    def test_minor_injury_green(self) -> None:
        patient = PatientData(
            chief_complaint="Torci o tornozelo jogando futebol",
            pain_scale=3,
        )
        result = mock_classify(patient)
        assert result.triage_color == TriageColor.GREEN

    def test_fever_yellow(self) -> None:
        patient = PatientData(
            chief_complaint="Febre alta e vômitos há 2 dias",
            pain_scale=4,
        )
        result = mock_classify(patient)
        assert result.triage_color == TriageColor.YELLOW

    def test_airway_red(self) -> None:
        patient = PatientData(chief_complaint="Patient choking, airway blocked")
        result = mock_classify(patient)
        assert result.triage_color == TriageColor.RED

    def test_spo2_red_flag_upgrades_to_orange(self) -> None:
        patient = PatientData(
            chief_complaint="Torci o tornozelo",
            vital_signs=VitalSigns(spo2=88.0),
        )
        result = mock_classify(patient)
        assert result.triage_color == TriageColor.ORANGE

    def test_high_heart_rate_upgrades(self) -> None:
        patient = PatientData(
            chief_complaint="Preciso renovar receita",
            vital_signs=VitalSigns(heart_rate=130),
        )
        result = mock_classify(patient)
        # HR > 120 should upgrade from BLUE to YELLOW
        assert result.triage_color == TriageColor.YELLOW

    def test_high_pain_scale_upgrades(self) -> None:
        patient = PatientData(
            chief_complaint="Torci o tornozelo",
            pain_scale=9,
        )
        result = mock_classify(patient)
        # Pain >= 8 should upgrade to at least ORANGE
        assert result.triage_color in (TriageColor.RED, TriageColor.ORANGE)

    def _classify_sample(self, name: str) -> TriageResult:
        """Helper: build PatientData from a sample case by name and classify."""
        case = next(c for c in SAMPLE_CASES if c["name"] == name)
        vs_kwargs = {}
        for field in [
            "heart_rate",
            "blood_pressure",
            "respiratory_rate",
            "temperature",
            "spo2",
            "glucose",
        ]:
            val = case.get(field)
            if val and val != 0 and val != 0.0:
                vs_kwargs[field] = val

        vital_signs = VitalSigns(**vs_kwargs) if vs_kwargs else None
        patient = PatientData(
            chief_complaint=case["chief_complaint"],
            pain_scale=case.get("pain_scale"),
            vital_signs=vital_signs,
            age=case.get("age"),
            sex=case.get("sex"),
        )
        return mock_classify(patient)

    def test_sample_maria_silva_orange(self) -> None:
        result = self._classify_sample("Maria Silva")
        assert result.triage_color == TriageColor.ORANGE

    def test_sample_joao_santos_yellow(self) -> None:
        result = self._classify_sample("João Santos")
        assert result.triage_color == TriageColor.YELLOW

    def test_sample_ana_oliveira_green(self) -> None:
        result = self._classify_sample("Ana Oliveira")
        assert result.triage_color == TriageColor.GREEN

    def test_sample_carlos_ferreira_blue(self) -> None:
        result = self._classify_sample("Carlos Ferreira")
        assert result.triage_color == TriageColor.BLUE

    def test_sample_lucia_pereira_orange(self) -> None:
        result = self._classify_sample("Lúcia Pereira")
        assert result.triage_color == TriageColor.ORANGE

    def test_all_sample_cases_have_valid_result(self) -> None:
        for case in SAMPLE_CASES:
            vs_kwargs = {}
            for field in [
                "heart_rate",
                "blood_pressure",
                "respiratory_rate",
                "temperature",
                "spo2",
                "glucose",
            ]:
                val = case.get(field)
                if val and val != 0 and val != 0.0:
                    vs_kwargs[field] = val

            vital_signs = VitalSigns(**vs_kwargs) if vs_kwargs else None

            patient = PatientData(
                chief_complaint=case["chief_complaint"],
                pain_scale=case.get("pain_scale"),
                vital_signs=vital_signs,
                age=case.get("age"),
                sex=case.get("sex"),
            )
            result = mock_classify(patient)
            assert isinstance(result, TriageResult)
            assert 0.0 <= result.confidence <= 1.0
            assert result.reasoning
            assert result.key_discriminators

    def test_confidence_in_range(self) -> None:
        patient = PatientData(chief_complaint="Dor abdominal")
        result = mock_classify(patient)
        assert 0.0 <= result.confidence <= 1.0

    def test_result_has_level_and_wait(self) -> None:
        patient = PatientData(chief_complaint="Febre")
        result = mock_classify(patient)
        assert result.triage_level
        assert result.max_wait_minutes >= 0


# ---------------------------------------------------------------------------
# Vital-sign boundary tests
# ---------------------------------------------------------------------------


class TestVitalSignBoundaries:
    """Verify that vital-sign red flags upgrade triage color correctly."""

    def _classify_with_vitals(self, **vs_kwargs: object) -> TriageResult:
        """Classify a BLUE-baseline patient with given vital signs."""
        patient = PatientData(
            chief_complaint="Preciso renovar receita",
            pain_scale=0,
            vital_signs=VitalSigns(**vs_kwargs),
        )
        return mock_classify(patient)

    def test_low_heart_rate_upgrades_to_yellow(self) -> None:
        result = self._classify_with_vitals(heart_rate=45)
        assert result.triage_color == TriageColor.YELLOW

    def test_high_heart_rate_upgrades_to_yellow(self) -> None:
        result = self._classify_with_vitals(heart_rate=125)
        assert result.triage_color == TriageColor.YELLOW

    def test_high_respiratory_rate_upgrades_to_yellow(self) -> None:
        result = self._classify_with_vitals(respiratory_rate=35)
        assert result.triage_color == TriageColor.YELLOW

    def test_low_respiratory_rate_upgrades_to_yellow(self) -> None:
        result = self._classify_with_vitals(respiratory_rate=8)
        assert result.triage_color == TriageColor.YELLOW

    def test_high_temperature_upgrades_to_yellow(self) -> None:
        result = self._classify_with_vitals(temperature=41.0)
        assert result.triage_color == TriageColor.YELLOW

    def test_low_temperature_upgrades_to_yellow(self) -> None:
        result = self._classify_with_vitals(temperature=34.0)
        assert result.triage_color == TriageColor.YELLOW

    def test_low_glucose_upgrades_to_yellow(self) -> None:
        result = self._classify_with_vitals(glucose=50.0)
        assert result.triage_color == TriageColor.YELLOW

    def test_high_glucose_upgrades_to_yellow(self) -> None:
        result = self._classify_with_vitals(glucose=450.0)
        assert result.triage_color == TriageColor.YELLOW

    def test_low_systolic_bp_upgrades_to_orange(self) -> None:
        result = self._classify_with_vitals(blood_pressure="80/50")
        assert result.triage_color == TriageColor.ORANGE

    def test_high_systolic_bp_upgrades_to_orange(self) -> None:
        result = self._classify_with_vitals(blood_pressure="210/110")
        assert result.triage_color == TriageColor.ORANGE

    def test_low_spo2_upgrades_to_orange(self) -> None:
        result = self._classify_with_vitals(spo2=90.0)
        assert result.triage_color == TriageColor.ORANGE


# ---------------------------------------------------------------------------
# mock_analyze_image
# ---------------------------------------------------------------------------


class TestMockAnalyzeImage:
    def test_returns_string(self) -> None:
        result = mock_analyze_image(b"fake image bytes")
        assert isinstance(result, str)

    def test_nonempty_finding(self) -> None:
        result = mock_analyze_image(b"fake", mime_type="image/jpeg")
        assert len(result) > 0

    def test_png_returns_finding(self) -> None:
        result = mock_analyze_image(b"fake", mime_type="image/png")
        assert len(result) > 0

    def test_unknown_mime_returns_default(self) -> None:
        result = mock_analyze_image(b"fake", mime_type="image/webp")
        assert len(result) > 0


# ---------------------------------------------------------------------------
# build_mock_fhir_bundle
# ---------------------------------------------------------------------------


class TestBuildMockFhirBundle:
    def _make_bundle(self) -> dict:
        patient = PatientData(
            chief_complaint="Dor no peito",
            vital_signs=VitalSigns(heart_rate=110, spo2=94.0),
        )
        result = mock_classify(patient)
        return build_mock_fhir_bundle(
            patient_name="Maria Silva",
            patient_age=55,
            patient_sex="F",
            patient_data=patient,
            triage_result=result,
        )

    def test_bundle_structure(self) -> None:
        bundle = self._make_bundle()
        assert bundle["resourceType"] == "Bundle"
        assert bundle["type"] == "collection"
        assert "timestamp" in bundle
        assert "entry" in bundle
        assert len(bundle["entry"]) >= 4

    def test_contains_patient_resource(self) -> None:
        bundle = self._make_bundle()
        types = [e["resource"]["resourceType"] for e in bundle["entry"]]
        assert "Patient" in types

    def test_contains_encounter(self) -> None:
        bundle = self._make_bundle()
        types = [e["resource"]["resourceType"] for e in bundle["entry"]]
        assert "Encounter" in types

    def test_contains_triage_observation(self) -> None:
        bundle = self._make_bundle()
        types = [e["resource"]["resourceType"] for e in bundle["entry"]]
        assert "Observation" in types

    def test_contains_condition(self) -> None:
        bundle = self._make_bundle()
        types = [e["resource"]["resourceType"] for e in bundle["entry"]]
        assert "Condition" in types

    def test_patient_name(self) -> None:
        bundle = self._make_bundle()
        patient = next(
            e["resource"]
            for e in bundle["entry"]
            if e["resource"]["resourceType"] == "Patient"
        )
        assert patient["name"][0]["text"] == "Maria Silva"

    def test_patient_gender(self) -> None:
        bundle = self._make_bundle()
        patient = next(
            e["resource"]
            for e in bundle["entry"]
            if e["resource"]["resourceType"] == "Patient"
        )
        assert patient["gender"] == "female"

    def test_vital_signs_in_observation(self) -> None:
        bundle = self._make_bundle()
        obs = next(
            e["resource"]
            for e in bundle["entry"]
            if e["resource"]["resourceType"] == "Observation"
        )
        component_codes = [c["code"]["text"] for c in obs["component"]]
        assert "Heart rate" in component_codes
        assert "SpO2" in component_codes


# ---------------------------------------------------------------------------
# SAMPLE_CASES
# ---------------------------------------------------------------------------


class TestSampleCases:
    def test_five_cases_defined(self) -> None:
        assert len(SAMPLE_CASES) == 5

    def test_all_have_required_fields(self) -> None:
        required = ["name", "age", "sex", "chief_complaint"]
        for case in SAMPLE_CASES:
            for field in required:
                assert field in case, f"Case {case.get('name')} missing {field}"

    def test_all_have_unique_names(self) -> None:
        names = [c["name"] for c in SAMPLE_CASES]
        assert len(names) == len(set(names))
