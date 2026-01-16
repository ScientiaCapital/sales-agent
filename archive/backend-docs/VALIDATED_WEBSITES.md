# Validated Company Websites

## Manually Verified ICPs (Dec 22, 2025)

These 7 companies were manually validated during scraper development.
All websites are confirmed good, active, and contain quality ICP signals.

| Company ID | Company Name | Website | ICP Tier | Notes |
|------------|--------------|---------|----------|-------|
| `f4e19975-0f94-4378-9697-d104095c2589` | ACTION AIR CON HEATING AND SOLAR | https://actionac.net | PLATINUM (80 pts) | Design-Build, Commercial HVAC, Generators, No hiring (careers 404) |
| `1ff68fe1-cb89-4207-972c-b48a9f90b39f` | BERKEYS A/C PLUMBING & ELECTRICAL | https://www.berkeys.com | SILVER (50 pts → 130+ expected) | ALL 9 MEP capabilities, MVP program, financing, specials |
| `abe09d67-6a64-4d48-8ac2-88cd9b50c745` | POSITIVE ENERGY ELECTRICAL, LLC | https://www.positiveee.com | SILVER (60 pts) | Residential + Commercial + **Industrial** (3 market segments) |
| `e7444082-7238-4a7b-bee6-3b4a14c68382` | RAVINIA PLUMBING HEATING & ELECTRIC | https://raviniaplumbing.com | SILVER (60 pts → 110+ expected) | Medical gas piping, commercial HVAC, 7/9 MEP, hiring |
| `58960d18-0ae0-43a2-addd-ed52b0d295f6` | Restano Heating, Cooling & Plumbing, Inc. | https://www.restano.com | None → 120+ expected | External careers (iCIMS), financing, 7/9 MEP, OEM partnerships |
| `b1143126-adf2-48e2-ae71-08b4daae82fd` | Raymond Plumbing and Heating Inc | https://www.raymondplumbing.com | None → 100+ expected | **OEM partnerships** (Carrier, Bradford White, Weil-McLain), Comfort Performance Plan, 24/7 service, hiring with 4 jobs |
| `11bbae76-f127-4643-9df2-c198deb16479` | Denron Hall Plumbing and HVAC LLC | https://denronhall.com | None → **115+ expected** | **ALL 5 HIGH-VALUE SIGNALS**: Design-Build, Engineering/CAD, Medical Gas, Building Automation, Awards |

## HIGH-VALUE Signal Distribution

| Company | Design-Build | Engineering | Medical | Automation | Industrial | Total HV |
|---------|--------------|-------------|---------|------------|------------|----------|
| ACTION AIR CON | ✅ | ❌ | ❌ | ❌ | ❌ | 1/5 |
| BERKEYS | ❌ | ❌ | ❌ | ❌ | ❌ | 0/5 |
| POSITIVE ENERGY | ❌ | ❌ | ❌ | ❌ | ✅ | 1/5 |
| RAVINIA | ❌ | ❌ | ✅ | ❌ | ❌ | 1/5 |
| RESTANO | ❌ | ❌ | ❌ | ❌ | ❌ | 0/5 |
| RAYMOND | ❌ | ❌ | ❌ | ❌ | ❌ | 0/5 |
| **DENRON HALL** | ✅ | ✅ | ✅ | ✅ | ❌ | **5/5** |

## Key Findings

### Denron Hall = PLATINUM Template
- Licensed Engineers mentioned in text
- CAD Department (in-house design capability)
- Medical Gas Piping (healthcare specialization)
- Building Automation/Controls (smart buildings)
- Design-Build (integrated approach)
- Preventative Maintenance + Emergency Service
- Multiple MEP capabilities
- Awards page exists

### Signal Patterns
- **External Careers Portals**: Restano uses careers-restano.icims.com (redirect detected successfully)
- **Hiring False Positives**: ACTION AIR CON careers page 404, but scraper correctly returned FALSE
- **Service Area Pages**: Multiple variants (`/service-areas/`, `/service-area/`)
- **OEM Partnerships**: Raymond has Carrier, Bradford White, Weil-McLain (certified installer status)
- **Market Segmentation**: POSITIVE ENERGY explicitly lists Residential, Commercial, Industrial pages

## Migration Order

1. ✅ `20251222_add_enrichment_columns.sql` - Basic enrichment + `is_hiring`, `has_maintenance_plan`
2. **NEW** `20251222_add_standard_signals.sql` - `has_generators`, `has_commercial`, `has_industrial`, `has_membership`, `has_specials`, `has_financing`
3. ✅ `20251222_add_high_value_signals.sql` - 7 HIGH-VALUE signals

## Next Steps

1. Run migration #2 (`20251222_add_standard_signals.sql`) in Supabase SQL Editor
2. Re-run enrichment script to save all 15 signals to database
3. Verify Denron Hall shows ~115 ICP points with new scoring
4. Batch enrich remaining 200 ICP companies with complete scraper
