from datetime import date
from decimal import Decimal

from care_pathway.claim_assignment import Claim, EpisodeDefinition, assign_claims
from care_pathway.cost_analysis import BenchmarkPrice, EpisodeCostItem, aggregate_episode_costs, detect_cost_outliers
from care_pathway.episode_details import ComplicationEvent, EpisodeAttribution, apply_episode_details
from care_pathway.episode_windows import EpisodeWindow


def main():
    episode_id = "knee-episode-1"
    patient_id = "patient-1"
    provider_id = "orthopedic-provider-1"
    diagnosis_codes = frozenset({"M17.11"})

    window = EpisodeWindow(
        index_date=date(2026, 3, 10),
        admission_date=date(2026, 3, 10),
        discharge_date=date(2026, 3, 13),
        preoperative_days=30,
        postacute_days=90,
    )
    episode = EpisodeDefinition(
        episode_id=episode_id,
        patient_id=patient_id,
        window=window,
        diagnosis_codes=diagnosis_codes,
        relevant_provider_ids=frozenset({provider_id}),
        index_procedure_code="KNEE-REPLACEMENT",
    )
    claims = [
        Claim("imaging-claim", patient_id, date(2026, 2, 20), diagnosis_codes, provider_id, Decimal("150.00"), procedure_code="IMAGING"),
        Claim("surgery-claim", patient_id, date(2026, 3, 10), diagnosis_codes, provider_id, Decimal("12000.00"), procedure_code="KNEE-REPLACEMENT"),
        Claim("facility-claim", patient_id, date(2026, 3, 11), diagnosis_codes, provider_id, Decimal("8000.00")),
        Claim("infection-readmission", patient_id, date(2026, 3, 25), diagnosis_codes, provider_id, Decimal("2500.00")),
        Claim("rehab-claim", patient_id, date(2026, 4, 2), diagnosis_codes, provider_id, Decimal("1200.00")),
    ]

    assignments = assign_claims(claims, [episode])
    assigned_ids = {assignment.claim_id for assignment in assignments}
    cost_bucket_by_claim = {
        "imaging-claim": "facility",
        "surgery-claim": "surgery",
        "facility-claim": "facility",
        "infection-readmission": "readmissions",
        "rehab-claim": "rehab",
    }
    cost_items = [
        EpisodeCostItem(
            episode_id=episode_id,
            episode_type="knee-replacement",
            claim_id=claim.claim_id,
            paid_amount=claim.paid_amount,
            cost_bucket=cost_bucket_by_claim[claim.claim_id],
        )
        for claim in claims
        if claim.claim_id in assigned_ids
    ]
    reports = aggregate_episode_costs(
        cost_items,
        [BenchmarkPrice("knee-replacement", Decimal("20000.00"))],
    )
    reports = apply_episode_details(
        reports,
        attributions=[EpisodeAttribution(episode_id, provider_id, "hospital-1")],
        complications=[
            ComplicationEvent(
                episode_id,
                "infection-readmission",
                "INFECTION",
                "Infection-related readmission on March 25",
            )
        ],
    )
    comparison_items = []
    for index, amount in enumerate((100, 110, 120, 130, 140), start=1):
        comparison_items.append(EpisodeCostItem(
            episode_id=f"comparison-{index}",
            episode_type="comparison",
            claim_id=f"comparison-claim-{index}",
            paid_amount=Decimal(amount),
            cost_bucket="surgery",
        ))
    comparison_reports = aggregate_episode_costs(
        comparison_items, [BenchmarkPrice("comparison", Decimal(200))]
    )
    reports = detect_cost_outliers([*reports, *comparison_reports])
    report = next(item for item in reports if item.episode_id == episode_id)

    print("Care Pathway and Episode-of-Care Builder")
    print(f"Episode: {report.episode_id}")
    print(f"Index date: {window.index_date}")
    print(f"Preoperative start: {window.preoperative_start}")
    print(f"Hospital stay: {window.hospital_start} to {window.hospital_end}")
    print(f"Post-acute end: {window.postacute_end}")
    print(f"Assigned claims: {len(assignments)}")
    print("\nCost by bucket:")
    for bucket, amount in report.bucket_totals.items():
        print(f"  {bucket}: ${amount:,.2f}")
    print(f"Total paid: ${report.total_paid:,.2f}")
    print(f"Benchmark: ${report.target_price:,.2f}")
    print(f"Above benchmark: {report.above_target}")
    print(f"Statistical outlier (2 SD): {report.outlier_2sd}")
    print(f"Statistical outlier (IQR): {report.outlier_iqr}")
    print(f"Complication identified: {report.complications}")
    print(f"Complication claims: {report.complication_claim_ids}")
    print(f"Responsible provider: {report.responsible_provider_id}")
    print(f"Responsible facility: {report.responsible_facility_id}")


if __name__ == "__main__":
    main()
