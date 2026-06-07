import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker

st.set_page_config(page_title="TechNova FinOps Dashboard v2", page_icon="☁️", layout="wide")

st.markdown("""
<style>
    .metric-card { background:#f8f9fa; border:1px solid #e0e0e0; border-radius:10px; padding:16px 20px; text-align:center; }
    .metric-label { font-size:13px; color:#666; margin-bottom:4px; }
    .metric-value { font-size:24px; font-weight:600; color:#1a1a1a; }
    .finding-box { background:#fff8f0; border-left:4px solid #EF9F27; border-radius:4px; padding:12px 16px; margin-bottom:10px; }
    .rec-box { background:#f0f9f4; border-left:4px solid #1D9E75; border-radius:4px; padding:12px 16px; margin-bottom:10px; }
</style>
""", unsafe_allow_html=True)

@st.cache_data
def load_data():
    billing   = pd.read_csv('v2_aws_billing.csv')
    usage     = pd.read_csv('v2_usage_metrics.csv')
    inventory = pd.read_csv('v2_resource_inventory.csv')

    # clean
    billing   = billing.drop_duplicates(subset=['resource_id','billing_period'])
    usage     = usage.drop_duplicates(subset=['resource_id','billing_period'])
    inventory = inventory.drop_duplicates(subset=['resource_id','billing_period'])

    billing['usage_start_date'] = pd.to_datetime(billing['usage_start_date'])
    billing['usage_end_date']   = pd.to_datetime(billing['usage_end_date'])

    env_map = {'prod':'production','production':'production','dev':'development','development':'development','staging':'staging'}
    billing['tag_environment'] = billing['tag_environment'].map(env_map)

    billing['tag_team']        = billing['tag_team'].fillna('untagged')
    billing['tag_environment'] = billing['tag_environment'].fillna('untagged')
    billing['tag_project']     = billing['tag_project'].fillna('untagged')
    inventory['owner_email']   = inventory['owner_email'].fillna('no-owner')
    inventory['cost_center']   = inventory['cost_center'].fillna('unassigned')
    inventory['environment']   = inventory['environment'].fillna('unknown')

    billing['cost_eur'] = (billing['unblended_cost'] * 0.92).round(2)

    # region tier
    region_tier = {'us-east-1':'low-cost','eu-west-1':'standard','eu-central-1':'standard','ap-southeast-1':'high-cost'}
    billing['region_tier'] = billing['region'].map(region_tier)

    # usage flags
    usage['is_idle'] = (usage['avg_cpu_utilization_pct'] < 10) & (usage['max_cpu_utilization_pct'] < 20)
    usage['safe_to_downsize'] = ((usage['avg_cpu_utilization_pct'] < 40) & (usage['max_cpu_utilization_pct'] < 60) &
                                  (usage['avg_memory_utilization_pct'] < 40) & (usage['max_memory_utilization_pct'] < 60))
    usage['memory_bound'] = (usage['avg_cpu_utilization_pct'] < 15) & (usage['avg_memory_utilization_pct'] > 75)
    def cat(c):
        if c < 10: return 'idle'
        elif c < 40: return 'underutilized'
        elif c < 80: return 'healthy'
        else: return 'high'
    usage['utilization_category'] = usage['avg_cpu_utilization_pct'].apply(cat)

    # merge
    df = billing.merge(inventory[['resource_id','billing_period','owner_email','cost_center','is_active']],
                       on=['resource_id','billing_period'], how='left')
    df = df.merge(usage[['resource_id','billing_period','instance_type','avg_cpu_utilization_pct',
                         'max_cpu_utilization_pct','avg_memory_utilization_pct','max_memory_utilization_pct',
                         'running_on_weekends','is_idle','safe_to_downsize','memory_bound','utilization_category']],
                  on=['resource_id','billing_period'], how='left')
    return df

df = load_data()

# Pre-compute
monthly = df.groupby('billing_period')['cost_eur'].sum().round(2).reset_index()
monthly.columns = ['month','total']
by_service = df.groupby('service')['cost_eur'].sum().sort_values(ascending=True)
by_team = df.groupby('tag_team')['cost_eur'].sum().sort_values(ascending=True)
by_region = df.groupby('region')['cost_eur'].sum().sort_values(ascending=True)
by_env = df.groupby('tag_environment')['cost_eur'].sum().sort_values(ascending=False)
by_pricing = df.groupby('pricing_term')['cost_eur'].sum()
untagged = df[df['tag_team']=='untagged'].groupby('service')['cost_eur'].sum().sort_values(ascending=True)
compute = df[df['avg_cpu_utilization_pct'].notna()]

total_spend = df['cost_eur'].sum()
untagged_total = df[df['tag_team']=='untagged']['cost_eur'].sum()
non_prod = df[df['tag_environment'].isin(['development','staging'])]['cost_eur'].sum()

st.title("☁️ TechNova GmbH — AWS FinOps Dashboard")
st.caption("Prepared by Cortex Reply FinOps Team · Jan–Jun 2024 · AWS · 5 teams · 4 regions · 10 services")
st.divider()

k1,k2,k3,k4,k5 = st.columns(5)
with k1: st.markdown(f'<div class="metric-card"><div class="metric-label">Total 6-Month Spend</div><div class="metric-value">€{total_spend:,.0f}</div></div>', unsafe_allow_html=True)
with k2: st.markdown(f'<div class="metric-card"><div class="metric-label">Untagged Spend</div><div class="metric-value" style="color:#E24B4A">€{untagged_total:,.0f}</div><div style="font-size:12px;color:#E24B4A">{untagged_total/total_spend*100:.0f}% of total</div></div>', unsafe_allow_html=True)
with k3: st.markdown(f'<div class="metric-card"><div class="metric-label">Non-Production Spend</div><div class="metric-value" style="color:#EF9F27">€{non_prod:,.0f}</div><div style="font-size:12px;color:#EF9F27">{non_prod/total_spend*100:.0f}% of total</div></div>', unsafe_allow_html=True)
with k4: st.markdown('<div class="metric-card"><div class="metric-label">Savings Potential</div><div class="metric-value" style="color:#1D9E75">€16,366</div><div style="font-size:12px;color:#1D9E75">43% reduction</div></div>', unsafe_allow_html=True)
with k5: st.markdown(f'<div class="metric-card"><div class="metric-label">Idle Resources</div><div class="metric-value" style="color:#E24B4A">{int(compute["is_idle"].sum())}</div><div style="font-size:12px;color:#E24B4A">at &lt;10% CPU</div></div>', unsafe_allow_html=True)

st.divider()

tab1,tab2,tab3,tab4,tab5,tab6 = st.tabs(["📈 Overview","👥 Teams & Regions","🌍 Environment","💰 Pricing","💻 Utilization","✅ Savings"])

def fmt(ax):
    ax.xaxis.set_major_formatter(mticker.FuncFormatter(lambda x,_: f'€{x:,.0f}'))

with tab1:
    c1,c2 = st.columns(2)
    with c1:
        st.subheader("Monthly Cost Trend")
        fig,ax = plt.subplots(figsize=(7,4))
        colors = ['#E24B4A' if m=='2024-04' else '#378ADD' for m in monthly['month']]
        ax.plot(monthly['month'], monthly['total'], marker='o', linewidth=2.5, color='#378ADD', markersize=8)
        ax.scatter(['2024-04'], monthly[monthly['month']=='2024-04']['total'], color='#E24B4A', s=120, zorder=5)
        ax.set_ylabel('Cost (EUR)'); ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x,_: f'€{x:,.0f}'))
        ax.grid(axis='y', alpha=0.3)
        plt.tight_layout(); st.pyplot(fig); plt.close()
    with c2:
        st.subheader("Cost by Service")
        fig,ax = plt.subplots(figsize=(7,4))
        ax.barh(by_service.index, by_service.values, color='#378ADD')
        fmt(ax)
        plt.tight_layout(); st.pyplot(fig); plt.close()
    st.markdown(f'<div class="finding-box"><b>Finding:</b> Spend is volatile, peaking at €8,000 in April. EC2 (€{by_service.max():,.0f}), S3 and CloudFront are the top 3 services — together 70% of all spend.</div>', unsafe_allow_html=True)

with tab2:
    c1,c2 = st.columns(2)
    with c1:
        st.subheader("Cost by Team")
        fig,ax = plt.subplots(figsize=(7,4))
        colors = ['#E24B4A' if t=='untagged' else '#378ADD' for t in by_team.index]
        ax.barh(by_team.index, by_team.values, color=colors)
        fmt(ax)
        plt.tight_layout(); st.pyplot(fig); plt.close()
    with c2:
        st.subheader("Cost by Region")
        fig,ax = plt.subplots(figsize=(7,4))
        rn = {'eu-central-1':'Frankfurt','eu-west-1':'Ireland','us-east-1':'Virginia','ap-southeast-1':'Singapore'}
        labels = [rn.get(r,r) for r in by_region.index]
        ax.barh(labels, by_region.values, color='#0D9488')
        fmt(ax)
        plt.tight_layout(); st.pyplot(fig); plt.close()
    st.markdown(f'<div class="finding-box"><b>Finding:</b> Untagged is the largest "team" at €{untagged_total:,.0f} ({untagged_total/total_spend*100:.0f}%). 51% of spend is in Frankfurt — a healthy distribution for an EU company.</div>', unsafe_allow_html=True)
    st.markdown('<div class="rec-box"><b>Recommendation:</b> Enforce tagging via AWS Config Rules. Prioritize EC2, CloudFront, and S3 in Frankfurt first.</div>', unsafe_allow_html=True)

with tab3:
    c1,c2 = st.columns([1,1])
    with c1:
        st.subheader("Cost by Environment")
        fig,ax = plt.subplots(figsize=(6,5))
        ce = {'production':'#1D9E75','development':'#EF9F27','staging':'#378ADD','untagged':'#E24B4A'}
        pie_colors = [ce.get(e,'#94A3B8') for e in by_env.index]
        ax.pie(by_env.values, labels=by_env.index, autopct='%1.1f%%', startangle=90, colors=pie_colors, textprops={'fontsize':11})
        plt.tight_layout(); st.pyplot(fig); plt.close()
    with c2:
        st.subheader("The non-production problem")
        st.metric("Non-Production Spend (dev + staging)", f"€{non_prod:,.0f}", f"{non_prod/total_spend*100:.1f}% of total")
        st.markdown(f"""
        - Development: €{df[df['tag_environment']=='development']['cost_eur'].sum():,.0f}
        - Staging: €{df[df['tag_environment']=='staging']['cost_eur'].sum():,.0f}
        - Production: €{df[df['tag_environment']=='production']['cost_eur'].sum():,.0f}

        Non-production is **higher than production** — a red flag. These environments run 24/7 but are only used during business hours.
        """)
    st.markdown('<div class="rec-box"><b>Recommendation:</b> Auto-shutdown dev/staging outside business hours (Mon–Fri 08:00–20:00). Estimated saving: €8,059 — the single biggest opportunity.</div>', unsafe_allow_html=True)

with tab4:
    st.subheader("Pricing Model Analysis")
    c1,c2 = st.columns([1,1])
    with c1:
        pricing_env = df.groupby(['tag_environment','pricing_term'])['cost_eur'].sum().round(2).reset_index()
        pivot = pricing_env.pivot(index='tag_environment', columns='pricing_term', values='cost_eur').fillna(0)
        fig,ax = plt.subplots(figsize=(7,4.5))
        pivot.plot(kind='bar', ax=ax, width=0.7, color={'OnDemand':'#E24B4A','Reserved':'#1D9E75','Spot':'#EF9F27'})
        ax.set_ylabel('Cost (EUR)'); ax.set_xlabel('')
        ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x,_: f'€{x:,.0f}'))
        ax.legend(title='Pricing'); ax.tick_params(axis='x', rotation=0)
        plt.tight_layout(); st.pyplot(fig); plt.close()
    with c2:
        st.markdown("#### Pricing breakdown")
        for term in ['OnDemand','Reserved','Spot']:
            val = by_pricing.get(term,0)
            st.metric(term, f"€{val:,.0f}", f"{val/total_spend*100:.0f}% of total")
    st.markdown('<div class="finding-box"><b>Finding:</b> Production relies too much on On-Demand (€5,597) vs Reserved (€4,676) — it runs 24/7 so should be mostly Reserved. Dev uses Spot well (€4,322) — keep that.</div>', unsafe_allow_html=True)
    st.markdown('<div class="rec-box"><b>Recommendation:</b> Move steady production On-Demand workloads to 1-year Reserved Instances. Saving: €2,238.</div>', unsafe_allow_html=True)

with tab5:
    st.subheader("Resource Utilization")
    c1,c2 = st.columns([1,1])
    with c1:
        cat_cost = compute.groupby('utilization_category')['cost_eur'].sum().reindex(['idle','underutilized','healthy','high']).fillna(0)
        fig,ax = plt.subplots(figsize=(7,4.5))
        bars = ax.bar(cat_cost.index, cat_cost.values, color=['#E24B4A','#EF9F27','#1D9E75','#378ADD'], width=0.6)
        ax.set_ylabel('Cost (EUR)'); ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x,_: f'€{x:,.0f}'))
        for b,v in zip(bars, cat_cost.values):
            ax.text(b.get_x()+b.get_width()/2, b.get_height()+30, f'€{v:,.0f}', ha='center', fontsize=9, fontweight='bold')
        plt.tight_layout(); st.pyplot(fig); plt.close()
    with c2:
        st.markdown("#### Rightsizing opportunities")
        st.metric("Idle resources (<10% CPU)", f"{int(compute['is_idle'].sum())}", f"€{compute[compute['is_idle']]['cost_eur'].sum():,.0f} wasted")
        st.metric("Safe to downsize (CPU + memory low)", f"{int(compute['safe_to_downsize'].sum())}", f"€{compute[compute['safe_to_downsize']]['cost_eur'].sum():,.0f}")
        st.metric("Memory-bound — DO NOT downsize", f"{int(compute['memory_bound'].sum())}", f"€{compute[compute['memory_bound']]['cost_eur'].sum():,.0f}", delta_color="off")
    st.markdown('<div class="finding-box"><b>Finding:</b> 17 resources are memory-bound — low CPU but high RAM. These look idle but must NOT be downsized or they will crash. Always check memory, not just CPU.</div>', unsafe_allow_html=True)

with tab6:
    st.subheader("Savings Opportunity Summary")
    c1,c2 = st.columns([1,1])
    with c1:
        fig,ax = plt.subplots(figsize=(7,4.5))
        savings = {'Auto-shutdown\ndev/staging':8059.28,'Rightsize\noverprovisioned':3287.20,'Shut down\nidle resources':2781.02,'Production →\nReserved':2238.73}
        labels,values = list(savings.keys()), list(savings.values())
        ax.barh(labels, values, color=['#E24B4A','#EF9F27','#8B5CF6','#1D9E75'])
        ax.set_xlabel('Savings (EUR)'); ax.xaxis.set_major_formatter(mticker.FuncFormatter(lambda x,_: f'€{x:,.0f}'))
        for i,v in enumerate(values):
            ax.text(v+100, i, f'€{v:,.0f}', va='center', fontsize=10, fontweight='bold')
        plt.tight_layout(); st.pyplot(fig); plt.close()
    with c2:
        st.markdown("#### Prioritized recommendations")
        sav_df = pd.DataFrame({
            'Action':['Auto-shutdown dev/staging','Rightsize overprovisioned','Shut down idle','Production → Reserved'],
            'Saving (€)':[8059,3287,2781,2239],
            'Effort':['Low','Medium','Low','Medium'],
            'Priority':['High','High','High','Medium']
        })
        st.dataframe(sav_df.style.format({'Saving (€)':'€{:,.0f}'}), use_container_width=True)
        a,b,c = st.columns(3)
        a.metric("Current Spend", f"€{total_spend:,.0f}")
        b.metric("Savings", "€16,366", "+43%")
        c.metric("Optimized", f"€{total_spend-16366:,.0f}", "-€16,366", delta_color="inverse")
    st.markdown('<div class="rec-box"><b>Conclusion:</b> TechNova can cut 43% of cloud spend. Priority order: (1) auto-shutdown non-prod, (2) enforce tagging, (3) rightsize + shut down idle, (4) optimize production pricing.</div>', unsafe_allow_html=True)
