"""
Jharkhand Education Budget Allocation Model
============================================
Kajal Kumari — Data-Driven Policy Framework

Purpose:
  Given a total education budget, determine the optimal allocation
  across all 24 Jharkhand districts to maximise dropout reduction.

Model Logic:
  1. Crisis Score      — how urgent is the need in each district?
  2. Efficiency Score  — how much impact does ₹1 crore have here?
  3. Priority Index    — combined ranking (Crisis 60% + Efficiency 40%)
  4. Budget Allocation — proportional to Priority Index
  5. Intervention Plan — specific spend on teachers + classrooms per district

Outputs:
  - jharkhand_budget_allocation.csv      → import into Tableau
  - jharkhand_intervention_detail.csv    → detailed cost breakdown
  - budget_model_summary.txt             → plain-English findings
"""

import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import warnings
warnings.filterwarnings('ignore')

# ── COST ASSUMPTIONS (based on Jharkhand govt data & RTE norms) ─────────────
TEACHER_COST_LAKHS       = 9.0   # ₹9 lakh/year per teacher (salary + benefits)
CLASSROOM_COST_LAKHS     = 4.0   # ₹4 lakh per smart classroom installation
RTE_PTR_NORM             = 30    # RTE mandated Pupil-Teacher Ratio
TARGET_SMART_CLASS_PCT   = 30.0  # Target: 30% of schools with smart classrooms
STUDENTS_PER_CLASSROOM   = 40    # Avg students per classroom

# ── WEIGHTS ──────────────────────────────────────────────────────────────────
# Crisis Score weights
W_HIDDEN_DROPOUT = 0.40
W_DROPOUT_MIDDLE = 0.30
W_PTR_SECONDARY  = 0.30

# Efficiency Score weights
W_INFRA_GAP      = 0.40   # Low smart classrooms = more room to improve
W_INTERNET_GAP   = 0.30   # Low internet = more room to improve
W_ENROLMENT      = 0.30   # Larger student population = more impact per rupee

# Priority Index weights
W_CRISIS      = 0.60
W_EFFICIENCY  = 0.40
# ─────────────────────────────────────────────────────────────────────────────


def normalise(series, invert=False):
    """Min-max normalise to 0–100. Invert=True for 'lower is better' metrics."""
    mn, mx = series.min(), series.max()
    if mx == mn:
        return pd.Series([50.0] * len(series), index=series.index)
    norm = (series - mn) / (mx - mn) * 100
    return 100 - norm if invert else norm


def compute_teachers_needed(row):
    """How many additional teachers are needed to reach PTR 30?"""
    if row['PTR_Secondary'] <= RTE_PTR_NORM:
        return 0
    # Students at secondary level ÷ target PTR = teachers needed
    # Current teachers at secondary ≈ secondary enrolment ÷ current PTR
    current_teachers = row['Enrolment_Secondary'] / row['PTR_Secondary']
    target_teachers  = row['Enrolment_Secondary'] / RTE_PTR_NORM
    return max(0, round(target_teachers - current_teachers))


def compute_classrooms_needed(row):
    """How many smart classrooms needed to reach 30% of schools?"""
    current_pct   = row['Pct_Smart_Classrooms']
    if current_pct >= TARGET_SMART_CLASS_PCT:
        return 0
    gap_pct       = TARGET_SMART_CLASS_PCT - current_pct
    schools_total = row['Total_Schools']
    return max(0, round((gap_pct / 100) * schools_total))


def main(total_budget_crore=500):

    # ── LOAD DATA ────────────────────────────────────────────────────────────
    df = pd.read_csv('/mnt/user-data/uploads/jharkhand_master_data.csv')
    df['District'] = df['District'].str.replace(r'\nD$', '', regex=True).str.strip()

    # ── STEP 1: CRISIS SCORE ─────────────────────────────────────────────────
    df['norm_hidden_dropout'] = normalise(df['Hidden_Dropout_Mid_to_Sec_Pct'])
    df['norm_dropout_middle'] = normalise(df['Dropout_Middle'])
    df['norm_ptr_secondary']  = normalise(df['PTR_Secondary'])

    df['Crisis_Score'] = (
        df['norm_hidden_dropout'] * W_HIDDEN_DROPOUT +
        df['norm_dropout_middle'] * W_DROPOUT_MIDDLE +
        df['norm_ptr_secondary']  * W_PTR_SECONDARY
    ).round(2)

    # ── STEP 2: EFFICIENCY SCORE ─────────────────────────────────────────────
    # Lower infrastructure = higher efficiency (more room to improve)
    df['norm_infra_gap']    = normalise(df['Pct_Smart_Classrooms'], invert=True)
    df['norm_internet_gap'] = normalise(df['Pct_Internet'],          invert=True)
    df['norm_enrolment']    = normalise(df['Total_Enrolment'])

    df['Efficiency_Score'] = (
        df['norm_infra_gap']    * W_INFRA_GAP    +
        df['norm_internet_gap'] * W_INTERNET_GAP +
        df['norm_enrolment']    * W_ENROLMENT
    ).round(2)

    # ── STEP 3: PRIORITY INDEX ───────────────────────────────────────────────
    df['Priority_Index'] = (
        df['Crisis_Score']     * W_CRISIS +
        df['Efficiency_Score'] * W_EFFICIENCY
    ).round(2)

    # ── STEP 4: BUDGET ALLOCATION ────────────────────────────────────────────
    total_priority = df['Priority_Index'].sum()
    df['Budget_Share_Pct']   = (df['Priority_Index'] / total_priority * 100).round(2)
    df['Budget_Crore']       = (df['Budget_Share_Pct'] / 100 * total_budget_crore).round(2)

    # ── STEP 5: INTERVENTION COST ESTIMATES ──────────────────────────────────
    df['Teachers_Needed']       = df.apply(compute_teachers_needed, axis=1)
    df['Teacher_Cost_Crore']    = (df['Teachers_Needed'] * TEACHER_COST_LAKHS / 100).round(2)

    df['Classrooms_Needed']     = df.apply(compute_classrooms_needed, axis=1)
    df['Classroom_Cost_Crore']  = (df['Classrooms_Needed'] * CLASSROOM_COST_LAKHS / 100).round(2)

    df['Total_Intervention_Cost_Crore'] = (
        df['Teacher_Cost_Crore'] + df['Classroom_Cost_Crore']
    ).round(2)

    # Budget sufficiency flag
    df['Budget_Covers_Cost'] = df.apply(
        lambda r: 'Fully covered' if r['Budget_Crore'] >= r['Total_Intervention_Cost_Crore']
                  else f"Gap: ₹{r['Total_Intervention_Cost_Crore'] - r['Budget_Crore']:.1f} Cr",
        axis=1
    )

    # Students impacted estimate
    # Assumption: each teacher retained reduces dropout by ~15 students/year
    # Each smart classroom reduces dropout by ~8 students/year
    df['Est_Students_Retained'] = (
        df['Teachers_Needed'] * 15 +
        df['Classrooms_Needed'] * 8
    ).astype(int)

    df['Cost_Per_Student_Retained_Rs'] = df.apply(
        lambda r: round((r['Budget_Crore'] * 1e7) / r['Est_Students_Retained'])
                  if r['Est_Students_Retained'] > 0 else 0,
        axis=1
    )

    # ── SORT BY PRIORITY ─────────────────────────────────────────────────────
    df = df.sort_values('Priority_Index', ascending=False).reset_index(drop=True)
    df['Priority_Rank'] = df.index + 1

    # ── TABLEAU OUTPUT CSV ───────────────────────────────────────────────────
    tableau_cols = [
        'Priority_Rank', 'District',
        'Crisis_Score', 'Efficiency_Score', 'Priority_Index',
        'Budget_Share_Pct', 'Budget_Crore',
        'Hidden_Dropout_Mid_to_Sec_Pct', 'Dropout_Middle', 'PTR_Secondary',
        'Pct_Smart_Classrooms', 'Pct_Internet',
        'Teachers_Needed', 'Teacher_Cost_Crore',
        'Classrooms_Needed', 'Classroom_Cost_Crore',
        'Total_Intervention_Cost_Crore',
        'Est_Students_Retained', 'Cost_Per_Student_Retained_Rs',
        'Budget_Covers_Cost', 'Total_Enrolment', 'Total_Schools',
    ]
    df[tableau_cols].to_csv('jharkhand_budget_allocation.csv', index=False)
    print("✓ Tableau CSV saved: jharkhand_budget_allocation.csv")

    # ── SUMMARY TEXT ─────────────────────────────────────────────────────────
    top5 = df.head(5)
    total_teachers  = df['Teachers_Needed'].sum()
    total_classrooms = df['Classrooms_Needed'].sum()
    total_teacher_cost = df['Teacher_Cost_Crore'].sum()
    total_classroom_cost = df['Classroom_Cost_Crore'].sum()
    total_students_retained = df['Est_Students_Retained'].sum()

    summary = f"""
{'='*65}
JHARKHAND EDUCATION BUDGET ALLOCATION MODEL
Total Budget: ₹{total_budget_crore} crore  |  24 Districts  |  UDISE+ 2024-25
{'='*65}

TOP 5 PRIORITY DISTRICTS
{'─'*65}
{'Rank':<5} {'District':<25} {'Priority':>10} {'Budget (Cr)':>12} {'Students Retained':>18}
{'─'*65}"""

    for _, row in top5.iterrows():
        summary += f"\n{int(row['Priority_Rank']):<5} {row['District']:<25} {row['Priority_Index']:>10.1f} {row['Budget_Crore']:>12.1f} {row['Est_Students_Retained']:>18,}"

    summary += f"""

{'─'*65}
STATEWIDE INTERVENTION REQUIREMENTS
{'─'*65}
Teachers needed (to reach PTR 30):     {total_teachers:,} teachers
Cost of teacher hiring:                 ₹{total_teacher_cost:.1f} crore/year

Smart classrooms needed (to reach 30%): {total_classrooms:,} classrooms
Cost of classroom installation:          ₹{total_classroom_cost:.1f} crore (one-time)

Total intervention cost:                 ₹{total_teacher_cost + total_classroom_cost:.1f} crore
Estimated students retained annually:   {total_students_retained:,} students

{'─'*65}
KEY INSIGHT
{'─'*65}
With ₹{total_budget_crore} crore allocated by Priority Index:
- Top 5 crisis districts receive {top5['Budget_Share_Pct'].sum():.1f}% of total budget
- Estimated {total_students_retained:,} students retained statewide per year
- Average cost per student retained: ₹{int(total_budget_crore*1e7/total_students_retained):,}

MOST EFFICIENT DISTRICT:
{df.loc[df['Cost_Per_Student_Retained_Rs'] > 0, 'District'].iloc[df.loc[df['Cost_Per_Student_Retained_Rs'] > 0, 'Cost_Per_Student_Retained_Rs'].argmin()]}
— lowest cost per student retained

HIGHEST PRIORITY:
{df.iloc[0]['District']} (Priority Index: {df.iloc[0]['Priority_Index']:.1f})
— receives ₹{df.iloc[0]['Budget_Crore']:.1f} crore ({df.iloc[0]['Budget_Share_Pct']:.1f}% of budget)
{'='*65}
"""
    print(summary)
    with open('budget_model_summary.txt', 'w') as f:
        f.write(summary)

    # ── CHARTS ───────────────────────────────────────────────────────────────
    CORAL='#D85A30'; TEAL='#1D9E75'; AMBER='#BA7517'; PURPLE='#7F77DD'; GRAY='#888780'

    fig, axes = plt.subplots(1, 3, figsize=(20, 8))
    fig.suptitle(
        f'Jharkhand Education Budget Allocation Model — ₹{total_budget_crore} Crore | UDISE+ 2024-25',
        fontsize=14, fontweight='bold', y=1.01
    )

    plot_df = df.sort_values('Budget_Crore', ascending=True)

    # Chart A — Budget allocation by district
    colors_a = [CORAL if r <= 5 else AMBER if r <= 10 else TEAL
                for r in plot_df['Priority_Rank']]
    bars = axes[0].barh(plot_df['District'], plot_df['Budget_Crore'],
                        color=colors_a, edgecolor='white', linewidth=0.4)
    for bar, val in zip(bars, plot_df['Budget_Crore']):
        axes[0].text(bar.get_width() + 0.3, bar.get_y() + bar.get_height()/2,
                     f'₹{val:.1f}Cr', va='center', fontsize=7.5, color='#444')
    axes[0].set_title('Budget Allocation by District\n(₹ Crore)', pad=10, fontsize=12, fontweight='bold')
    axes[0].set_xlabel('Allocated budget (₹ Crore)')
    axes[0].tick_params(axis='y', labelsize=8.5)
    axes[0].set_xlim(0, plot_df['Budget_Crore'].max() * 1.2)
    patch1 = mpatches.Patch(color=CORAL, label='Top 5 — critical priority')
    patch2 = mpatches.Patch(color=AMBER, label='Ranks 6–10 — high priority')
    patch3 = mpatches.Patch(color=TEAL,  label='Ranks 11–24 — moderate')
    axes[0].legend(handles=[patch1, patch2, patch3], fontsize=8, loc='lower right')

    # Chart B — Crisis vs Efficiency scatter (bubble = budget)
    scatter = axes[1].scatter(
        df['Efficiency_Score'], df['Crisis_Score'],
        s=df['Budget_Crore'] * 8,
        c=df['Priority_Index'],
        cmap='RdYlGn_r',
        alpha=0.8, edgecolors='white', linewidth=0.7
    )
    for _, row in df.iterrows():
        if row['Priority_Rank'] <= 7:
            axes[1].annotate(
                row['District'],
                (row['Efficiency_Score'], row['Crisis_Score']),
                textcoords='offset points', xytext=(5, 3),
                fontsize=7.5, color='#333'
            )
    axes[1].axhline(df['Crisis_Score'].median(), color=GRAY,
                    linewidth=0.8, linestyle='--', alpha=0.5, label='Median crisis')
    axes[1].axvline(df['Efficiency_Score'].median(), color=GRAY,
                    linewidth=0.8, linestyle='--', alpha=0.5, label='Median efficiency')
    axes[1].set_xlabel('Efficiency Score (0–100)\nHigher = more impact per rupee')
    axes[1].set_ylabel('Crisis Score (0–100)\nHigher = more urgent need')
    axes[1].set_title('Crisis vs Efficiency Matrix\n(bubble size = budget allocated)', pad=10, fontsize=12, fontweight='bold')
    axes[1].legend(fontsize=8)
    plt.colorbar(scatter, ax=axes[1], label='Priority Index', shrink=0.8)

    # Quadrant labels
    axes[1].text(75, 85, 'HIGH need\nHIGH efficiency\n→ TOP PRIORITY',
                 fontsize=7.5, color=CORAL, alpha=0.7, ha='center',
                 bbox=dict(boxstyle='round,pad=0.3', facecolor='#FAECE7', alpha=0.5))
    axes[1].text(25, 85, 'HIGH need\nLOW efficiency',
                 fontsize=7.5, color=AMBER, alpha=0.7, ha='center',
                 bbox=dict(boxstyle='round,pad=0.3', facecolor='#FAEEDA', alpha=0.5))
    axes[1].text(75, 15, 'LOW need\nHIGH efficiency',
                 fontsize=7.5, color=TEAL, alpha=0.7, ha='center',
                 bbox=dict(boxstyle='round,pad=0.3', facecolor='#E1F5EE', alpha=0.5))

    # Chart C — Intervention breakdown (stacked bar)
    top10 = df.head(10).sort_values('Budget_Crore', ascending=True)
    axes[2].barh(top10['District'], top10['Teacher_Cost_Crore'],
                 color=CORAL, label='Teacher hiring cost', edgecolor='white', linewidth=0.4)
    axes[2].barh(top10['District'], top10['Classroom_Cost_Crore'],
                 left=top10['Teacher_Cost_Crore'],
                 color=PURPLE, label='Smart classroom cost', edgecolor='white', linewidth=0.4)
    axes[2].barh(top10['District'], top10['Budget_Crore'],
                 color='none', edgecolor=TEAL, linewidth=1.5,
                 label='Budget allocated', linestyle='--')
    axes[2].set_title('Intervention Cost vs Budget\n(Top 10 Priority Districts)', pad=10, fontsize=12, fontweight='bold')
    axes[2].set_xlabel('₹ Crore')
    axes[2].tick_params(axis='y', labelsize=8.5)
    axes[2].legend(fontsize=8)

    plt.tight_layout()
    plt.savefig('chart4_budget_allocation.png', dpi=150, bbox_inches='tight')
    print("✓ Chart saved: chart4_budget_allocation.png")

    return df


if __name__ == "__main__":
    print("Running Budget Allocation Model...\n")
    print("Budget scenario: ₹500 crore\n")
    result = main(total_budget_crore=500)
    print(f"\n✓ All outputs saved.")
    print(f"  → jharkhand_budget_allocation.csv  (import to Tableau)")
    print(f"  → budget_model_summary.txt         (key findings)")
    print(f"  → chart4_budget_allocation.png     (3 analysis charts)")
