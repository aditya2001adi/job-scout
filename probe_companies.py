"""
Probe script: test which companies in the cleantech / construction space
use Greenhouse or Ashby ATS by hitting their API endpoints.

Usage:
    python3 probe_companies.py               # probe everything
    python3 probe_companies.py --output      # also write job_boards.csv
"""
import csv
import sys
import time
from pathlib import Path
from typing import Optional
import requests

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
    "Accept": "application/json",
}

# ---------------------------------------------------------------------------
# Seed list: (display_name, industry, [greenhouse_slugs], [ashby_slugs])
# Multiple slug variants are tried in order; first hit wins.
# ---------------------------------------------------------------------------
CANDIDATES = [
    # ── Solar Developers / IPPs ──────────────────────────────────────────────
    ("Nexamp", "solar energy", ["nexamp"], ["nexamp"]),
    ("Apex Clean Energy", "renewable energy", ["apexcleanenergy", "apex-clean-energy"], ["apexcleanenergy"]),
    ("Cypress Creek Renewables", "solar energy", ["cypresscreekrenewables", "cypress-creek-renewables"], ["cypresscreekrenewables"]),
    ("Borrego", "solar energy", ["borrego", "borregosolar"], ["borrego"]),
    ("Solv Energy", "solar energy", ["solvenergy", "solv-energy"], ["solvenergy"]),
    ("8minute Solar Energy", "solar energy", ["8minuteenergy", "8minutesolarenergy"], ["8minuteenergy"]),
    ("Intersect Power", "solar energy", ["intersectpower"], ["intersectpower"]),
    ("Terra-Gen", "renewable energy", ["terragenpower", "terra-gen"], ["terragenpower"]),
    ("Origis Energy", "solar energy", ["origis", "origisenergy"], ["origis"]),
    ("Hecate Energy", "renewable energy", ["hecateenergy", "hecate-energy"], ["hecateenergy"]),
    ("Longroad Energy", "renewable energy", ["longroad", "longroad-energy"], ["longroad"]),
    ("Greenbacker Renewable Energy", "renewable energy", ["greenbacker"], ["greenbacker"]),
    ("Sunrock Distributed Generation", "solar energy", ["sunrock"], ["sunrock"]),
    ("CleanCapital", "solar energy", ["cleancapital"], ["cleancapital"]),
    ("Dimension Renewable Energy", "renewable energy", ["dimensionrenewable"], ["dimensionrenewable"]),
    ("Coronal Energy", "solar energy", ["coronalenergy"], ["coronalenergy"]),
    ("D.E. Shaw Renewable Investments", "renewable energy", ["desri"], ["desri"]),
    ("Inari Energy", "solar energy", ["inarienergy", "inari-energy"], ["inarienergy"]),
    ("ECP Environmental Growth Funds", "renewable energy", ["ecpenvironmental"], ["ecpenvironmental"]),
    ("Agilitas Energy", "solar energy", ["agilitasenergy"], ["agilitasenergy"]),
    ("Altus Power", "solar energy", ["altuspower", "altus-power"], ["altuspower"]),
    ("Sunstone Credit", "solar energy", ["sunstonecredit"], ["sunstonecredit"]),
    ("Energix Renewables", "renewable energy", ["energixrenewables"], ["energixrenewables"]),
    ("Soltage", "solar energy", ["soltage"], ["soltage"]),
    ("REsurety", "renewable energy", ["resurety"], ["resurety"]),
    ("kWh Analytics", "renewable energy", ["kwhanalytics"], ["kwhanalytics"]),
    ("National Grid Renewables", "renewable energy", ["nationalgridrenewables"], ["nationalgridrenewables"]),

    # ── Residential Solar ────────────────────────────────────────────────────
    ("Sunrun", "residential solar", ["sunrun"], ["sunrun"]),
    ("Sunnova Energy", "residential solar", ["sunnova"], ["sunnova"]),
    ("Elevation Solar", "residential solar", ["elevationsolar", "elevation-solar"], ["elevationsolar"]),
    ("Complete Solar", "residential solar", ["completesolar"], ["completesolar"]),
    ("Palmetto", "residential solar", ["palmetto", "palmettoclean"], ["palmetto"]),
    ("Lumio", "residential solar", ["lumio"], ["lumio"]),
    ("PosiGen", "residential solar", ["posigen"], ["posigen"]),
    ("Sunder Energy", "residential solar", ["sunderenergy"], ["sunderenergy"]),
    ("EnergySage", "solar marketplace", ["energysage"], ["energysage"]),
    ("GoodLeap", "solar financing", ["goodleap"], ["goodleap"]),
    ("Mosaic Solar", "solar financing", ["mosaic"], ["mosaic"]),
    ("Trinity Solar", "residential solar", ["trinitysolar"], ["trinitysolar"]),
    ("Freedom Forever", "residential solar", ["freedomforever"], ["freedomforever"]),
    ("Project Solar", "residential solar", ["projectsolar"], ["projectsolar"]),
    ("Perch Energy", "community solar", ["perchenergy"], ["perchenergy"]),
    ("Nexus Energy Group", "solar energy", ["nexusenergy"], ["nexusenergy"]),
    ("Sun Badger Solar", "residential solar", ["sunbadgersolar"], ["sunbadgersolar"]),

    # ── Battery Storage / BESS ───────────────────────────────────────────────
    ("Form Energy", "energy storage", ["formenergy"], ["formenergy"]),
    ("Fluence Energy", "energy storage", ["fluenceenergy", "fluence"], ["fluenceenergy", "fluence"]),
    ("Stem Inc", "energy storage", ["stem"], ["stem"]),
    ("Plus Power", "energy storage", ["pluspower"], ["pluspower"]),
    ("Powin", "energy storage", ["powin"], ["powin"]),
    ("Spearmint Energy", "energy storage", ["spearmint"], ["spearmint"]),
    ("Broad Reach Power", "energy storage", ["broadreachpower"], ["broadreachpower"]),
    ("Eos Energy Enterprises", "energy storage", ["eosenergy"], ["eosenergy"]),
    ("ESS Tech", "energy storage", ["esstech"], ["esstech"]),
    ("Energy Vault", "energy storage", ["energyvault"], ["energyvault"]),
    ("Hydrostor", "energy storage", ["hydrostor"], ["hydrostor"]),
    ("Nuvation Energy", "energy storage", ["nuvation"], ["nuvation"]),
    ("Key Capture Energy", "energy storage", ["keycaptureener", "keycaptureenergy"], ["keycaptureenergy"]),
    ("Glidepath Power", "energy storage", ["glidepathpower"], ["glidepathpower"]),
    ("Electriq Power", "energy storage", ["electriqpower"], ["electriqpower"]),
    ("Wärtsilä Energy", "energy storage", ["wartsila"], ["wartsila"]),

    # ── Wind ─────────────────────────────────────────────────────────────────
    ("Vineyard Wind", "offshore wind", ["vineyardwind"], ["vineyardwind"]),
    ("Orion Renewable Energy Group", "wind energy", ["orionrenewable"], ["orionrenewable"]),
    ("Avangrid Renewables", "wind energy", ["avangrid"], ["avangrid"]),
    ("New Leaf Energy", "renewable energy", ["newleafenergy"], ["newleafenergy"]),
    ("Enel Green Power North America", "renewable energy", ["enelgreenpower"], ["enelgreenpower"]),
    ("RWE Clean Energy", "renewable energy", ["rwecleanenergy", "rwe"], ["rwecleanenergy"]),
    ("Ørsted US", "offshore wind", ["orsted"], ["orsted"]),
    ("Invenergy", "renewable energy", ["invenergy"], ["invenergy"]),
    ("Pattern Energy", "renewable energy", ["patternenergy"], ["patternenergy"]),

    # ── EV Charging ──────────────────────────────────────────────────────────
    ("ChargePoint", "EV charging", ["chargepoint"], ["chargepoint"]),
    ("EVgo", "EV charging", ["evgo"], ["evgo"]),
    ("Blink Charging", "EV charging", ["blinkcharging"], ["blinkcharging"]),
    ("Electrify America", "EV charging", ["electrifyamerica"], ["electrifyamerica"]),
    ("EVCS", "EV charging", ["evcs"], ["evcs"]),
    ("FLO", "EV charging", ["flo", "addenergie"], ["flo"]),
    ("WattEV", "EV charging", ["wattev"], ["wattev"]),
    ("Xeal", "EV charging", ["xeal"], ["xeal"]),
    ("Nuvve", "EV charging", ["nuvve"], ["nuvve"]),
    ("EV Connect", "EV charging", ["evconnect"], ["evconnect"]),
    ("Ridgeline Energy Services", "EV charging", ["ridgelineenergy"], ["ridgelineenergy"]),
    ("PowerFlex", "EV charging + solar", ["powerflex"], ["powerflex"]),
    ("Rivian", "EVs", ["rivian"], ["rivian"]),

    # ── Grid / Energy Software ───────────────────────────────────────────────
    ("Aurora Solar", "solar software", ["aurorasolar"], ["aurorasolar"]),
    ("Arcadia", "energy software", ["arcadia"], ["arcadia"]),
    ("Raptor Maps", "solar software", ["raptormaps"], ["raptormaps"]),
    ("Sense", "home energy", ["sense"], ["sense"]),
    ("AutoGrid", "grid software", ["autogrid"], ["autogrid"]),
    ("Voltus", "demand response", ["voltus"], ["voltus"]),
    ("Leap Energy", "energy markets", ["leapenergy", "leap"], ["leapenergy", "leap"]),
    ("OhmConnect", "demand response", ["ohmconnect"], ["ohmconnect"]),
    ("Omnidian", "solar monitoring", ["omnidian"], ["omnidian"]),
    ("Scanifly", "solar software", ["scanifly"], ["scanifly"]),
    ("Gridmatic", "energy software", ["gridmatic"], ["gridmatic"]),
    ("Virtual Peaker", "grid software", ["virtualpeaker"], ["virtualpeaker"]),
    ("Swell Energy", "virtual power plants", ["swellenergy"], ["swellenergy"]),
    ("ClimateAI", "climate tech", ["climateai"], ["climateai"]),
    ("GridPoint", "energy management", ["gridpoint"], ["gridpoint"]),
    ("Bidgee", "energy software", ["bidgee"], ["bidgee"]),
    ("UtilityAPI", "energy data", ["utilityapi"], ["utilityapi"]),
    ("Recurve Analytics", "energy efficiency", ["recurve"], ["recurve"]),
    ("Volterra", "grid software", ["volterraenergy"], ["volterraenergy"]),
    ("SparkCognition", "industrial AI", ["sparkcognition"], ["sparkcognition"]),
    ("Powerley", "energy software", ["powerley"], ["powerley"]),
    ("Uplight", "utility software", ["uplight"], ["uplight"]),
    ("Itron", "grid hardware/software", ["itron"], ["itron"]),
    ("Enbala", "grid software", ["enbala"], ["enbala"]),
    ("Electron", "energy markets", ["electron"], ["electron"]),
    ("Bayou Energy", "energy data", ["bayouenergy"], ["bayouenergy"]),
    ("Extensible Energy", "demand response", ["extensibleenergy"], ["extensibleenergy"]),

    # ── Hydrogen / Other Clean Energy ────────────────────────────────────────
    ("Plug Power", "hydrogen", ["plugpower"], ["plugpower"]),
    ("Nel Hydrogen", "hydrogen", ["nel"], ["nel"]),
    ("Bloom Energy", "fuel cells", ["bloomenergy"], ["bloomenergy"]),
    ("Electric Hydrogen", "green hydrogen", ["electrichydrogen"], ["electrichydrogen"]),
    ("Verdagy", "green hydrogen", ["verdagy"], ["verdagy"]),
    ("Ohmium", "green hydrogen", ["ohmium"], ["ohmium"]),
    ("Syzygy Plasmonics", "clean energy", ["syzygy"], ["syzygy"]),
    ("Rondo Energy", "clean energy", ["rondoenergy"], ["rondoenergy"]),
    ("Antora Energy", "clean energy", ["antoraenergy"], ["antoraenergy"]),
    ("Electrasteel", "green steel", ["electrasteel"], ["electrasteel"]),
    ("Boston Metal", "green steel", ["bostonmetal"], ["bostonmetal"]),
    ("Electra", "green iron", ["electra"], ["electra"]),

    # ── Clean Energy Finance / Infra ─────────────────────────────────────────
    ("Generate Capital", "clean energy finance", ["generatecapital"], ["generatecapital"]),
    ("Hannon Armstrong", "clean energy finance", ["hannonarmstrong"], ["hannonarmstrong"]),
    ("Mosaic", "clean energy finance", ["mosaic"], ["mosaic"]),
    ("Loanpal", "solar financing", ["loanpal"], ["loanpal"]),
    ("Anza Renewables", "renewable energy", ["anzarenewables"], ["anzarenewables"]),
    ("Omnidian", "solar asset mgmt", ["omnidian"], ["omnidian"]),
    ("Atmos Financial", "clean finance", ["atmos"], ["atmos"]),

    # ── Large-Scale / Industrial Construction ────────────────────────────────
    ("Mortenson", "construction", ["mortenson"], ["mortenson"]),
    ("Sundt Construction", "construction", ["sundt"], ["sundt"]),
    ("McCarthy Building Companies", "construction", ["mccarthybuildingcompanies", "mccarthybuilding"], ["mccarthybuilding"]),
    ("DPR Construction", "construction", ["dpr"], ["dpr"]),
    ("JE Dunn Construction", "construction", ["jedunnconstruction", "jedunn"], ["jedunn"]),
    ("PCL Construction", "construction", ["pcl"], ["pcl"]),
    ("Gilbane Building Company", "construction", ["gilbane"], ["gilbane"]),
    ("Clark Construction", "construction", ["clarkconstructiongroup", "clark"], ["clark"]),
    ("Lendlease", "construction", ["lendlease"], ["lendlease"]),
    ("Walsh Group", "construction", ["walshgroup"], ["walshgroup"]),
    ("Hensel Phelps", "construction", ["henselphelps"], ["henselphelps"]),
    ("STRUCTURE Tone", "construction", ["structuretone"], ["structuretone"]),
    ("Brasfield & Gorrie", "construction", ["brasfieldgorrie"], ["brasfieldgorrie"]),
    ("Webcor", "construction", ["webcor"], ["webcor"]),
    ("Swinerton", "construction", ["swinerton"], ["swinerton"]),
    ("Kitchell", "construction", ["kitchell"], ["kitchell"]),
    ("Ryan Companies", "construction", ["ryan", "ryancompanies"], ["ryan"]),
    ("Robins & Morton", "construction", ["robinsmorton"], ["robinsmorton"]),
    ("Balfour Beatty US", "construction", ["balfourbeatty"], ["balfourbeatty"]),
    ("Turner Construction", "construction", ["turnerconstruction", "turner"], ["turnerconstruction"]),
    ("Skanska USA", "construction", ["skanska"], ["skanska"]),
    ("Consigli Construction", "construction", ["consigli"], ["consigli"]),
    ("Pepper Construction", "construction", ["pepperconstruction"], ["pepperconstruction"]),
    ("Manhattan Construction", "construction", ["manhattanconstruction"], ["manhattanconstruction"]),
    ("Barton Malow", "construction", ["bartonmalow"], ["bartonmalow"]),
    ("Boldt Construction", "construction", ["boldt"], ["boldt"]),
    ("Messer Construction", "construction", ["messerconstruction"], ["messerconstruction"]),
    ("Hoar Construction", "construction", ["hoarconstruction"], ["hoarconstruction"]),
    ("Clayco", "construction", ["clayco"], ["clayco"]),
    ("Whiting-Turner", "construction", ["whitingturner"], ["whitingturner"]),
    ("Holder Construction", "construction", ["holderconstruction"], ["holderconstruction"]),
    ("CBRE Build", "construction", ["cbrebuild"], ["cbrebuild"]),
    ("Greystar", "construction + real estate", ["greystar"], ["greystar"]),
    ("Related Companies", "real estate + construction", ["related"], ["related"]),
    ("Hines", "real estate + construction", ["hines"], ["hines"]),
    ("Suffolk Construction", "construction", ["suffolk"], ["suffolk"]),
    ("Devcon Construction", "construction", ["devcon"], ["devcon"]),

    # ── Residential Homebuilders ─────────────────────────────────────────────
    ("Toll Brothers", "homebuilder", ["tollbrothers"], ["tollbrothers"]),
    ("Taylor Morrison", "homebuilder", ["taylormorrison"], ["taylormorrison"]),
    ("Century Communities", "homebuilder", ["centurycommunities"], ["centurycommunities"]),
    ("Tri Pointe Homes", "homebuilder", ["tripointe"], ["tripointe"]),
    ("Meritage Homes", "homebuilder", ["meritagehomes"], ["meritagehomes"]),
    ("LGI Homes", "homebuilder", ["lgihomes"], ["lgihomes"]),
    ("Smith Douglas Homes", "homebuilder", ["smithdouglashomes"], ["smithdouglashomes"]),
    ("Dream Finders Homes", "homebuilder", ["dreamfindershomes"], ["dreamfindershomes"]),
    ("Green Brick Partners", "homebuilder", ["greenbrickpartners"], ["greenbrickpartners"]),
    ("Stanley Martin Homes", "homebuilder", ["stanleymartin"], ["stanleymartin"]),
    ("Forestar Group", "homebuilder", ["forestar"], ["forestar"]),
    ("Landsea Homes", "homebuilder", ["landscahomes", "landscaholdings"], ["landscahomes"]),
    ("William Lyon Homes", "homebuilder", ["williamlyonhomes"], ["williamlyonhomes"]),
    ("Shea Homes", "homebuilder", ["sheahomes"], ["sheahomes"]),
    ("David Weekley Homes", "homebuilder", ["davidweekleyhomes"], ["davidweekleyhomes"]),
    ("Comstock Companies", "homebuilder", ["comstock"], ["comstock"]),

    # ── Infrastructure EPC / Specialty Contractors ──────────────────────────
    ("MYR Group", "electrical contractor", ["myrgroup"], ["myrgroup"]),
    ("Primoris Services", "infrastructure", ["primorisservices", "primoris"], ["primoris"]),
    ("MasTec", "infrastructure", ["mastec"], ["mastec"]),
    ("Granite Construction", "infrastructure", ["granite"], ["granite"]),
    ("Wanzek Construction", "wind/solar EPC", ["wanzek"], ["wanzek"]),
    ("Blattner Energy", "renewable EPC", ["blattner"], ["blattner"]),
    ("IEA Energy Services", "renewable EPC", ["ieaenergy"], ["ieaenergy"]),
    ("Rosendin Electric", "electrical contractor", ["rosendin"], ["rosendin"]),
    ("Cupertino Electric", "electrical contractor", ["cupertinoelectric"], ["cupertinoelectric"]),
    ("Faith Technologies", "electrical contractor", ["faithtechnologies"], ["faithtechnologies"]),
    ("SOLV Energy", "solar EPC", ["solvenergy"], ["solvenergy"]),
    ("RES Americas", "renewable EPC", ["res"], ["res"]),
    ("juwi", "renewable EPC", ["juwi"], ["juwi"]),
    ("sPower", "renewable energy", ["spower"], ["spower"]),

    # ── Proptech / Real Estate Tech Adjacent ────────────────────────────────
    ("Lessen", "property services", ["lessen"], ["lessen"]),
    ("Thumbtack", "home services", ["thumbtack"], ["thumbtack"]),
    ("Angi", "home services", ["angi"], ["angi"]),
    ("Opendoor", "real estate tech", ["opendoor"], ["opendoor"]),
    ("Offerpad", "real estate tech", ["offerpad"], ["offerpad"]),
    ("Divvy Homes", "rent-to-own", ["divvy"], ["divvy"]),
    ("Orchard", "real estate tech", ["orchard"], ["orchard"]),

    # ── Climate Tech / Carbon / Sustainability ───────────────────────────────
    ("Watershed", "carbon management", ["watershed"], ["watershed"]),
    ("Xpansiv", "carbon markets", ["xpansiv"], ["xpansiv"]),
    ("South Pole", "carbon projects", ["southpole"], ["southpole"]),
    ("Redwood Materials", "battery recycling", ["redwoodmaterials"], ["redwoodmaterials"]),
    ("Li-Cycle", "battery recycling", ["licycle"], ["licycle"]),
    ("Nth Cycle", "clean metals", ["nthcycle"], ["nthcycle"]),
    ("Cirba Solutions", "battery recycling", ["cirbasolutions"], ["cirbasolutions"]),
    ("RePurpose Energy", "battery reuse", ["repurposeenergy"], ["repurposeenergy"]),
    ("Pearl Certification", "home efficiency", ["pearl"], ["pearl"]),
    ("Sealed", "home efficiency", ["sealed"], ["sealed"]),
    ("Ciara", "building efficiency", ["ciara"], ["ciara"]),
    ("BlocPower", "building electrification", ["blocpower"], ["blocpower"]),
    ("Sealed Air", "sustainability", ["sealedair"], ["sealedair"]),
    ("CarbonCure Technologies", "concrete tech", ["carboncure"], ["carboncure"]),
    ("Fortera", "green cement", ["fortera"], ["fortera"]),
    ("Brimstone", "green cement", ["brimstone"], ["brimstone"]),
    ("CarbonBuilt", "green cement", ["carbonbuilt"], ["carbonbuilt"]),
    ("Heirloom Carbon", "carbon removal", ["heirloom"], ["heirloom"]),
    ("Charm Industrial", "carbon removal", ["charmindustrial"], ["charmindustrial"]),
    ("Sustaera", "carbon removal", ["sustaera"], ["sustaera"]),
    ("Running Tide", "carbon removal", ["runningtide"], ["runningtide"]),
]


def probe_greenhouse(slug: str, session: requests.Session) -> bool:
    url = f"https://boards-api.greenhouse.io/v1/boards/{slug}/departments"
    try:
        r = session.get(url, timeout=10)
        return r.status_code == 200
    except Exception:
        return False


def probe_ashby(slug: str, session: requests.Session) -> bool:
    url = f"https://api.ashbyhq.com/posting-api/job-board/{slug}"
    try:
        r = session.get(url, timeout=10)
        return r.status_code == 200
    except Exception:
        return False


def main():
    write_csv = "--output" in sys.argv
    session = requests.Session()
    session.headers.update(HEADERS)

    results = []
    not_found = []
    total = len(CANDIDATES)

    print(f"Probing {total} candidate companies...\n")

    for i, (name, industry, gh_slugs, ashby_slugs) in enumerate(CANDIDATES):
        found_ats = None
        found_slug = None
        found_url = None

        # Try Greenhouse first
        for slug in gh_slugs:
            if probe_greenhouse(slug, session):
                found_ats = "Greenhouse"
                found_slug = slug
                found_url = f"https://boards.greenhouse.io/{slug}"
                break
            time.sleep(0.05)

        # If not Greenhouse, try Ashby
        if not found_ats:
            for slug in ashby_slugs:
                if probe_ashby(slug, session):
                    found_ats = "Ashby"
                    found_slug = slug
                    found_url = f"https://jobs.ashbyhq.com/{slug}"
                    break
                time.sleep(0.05)

        if found_ats:
            status = f"✓ {found_ats} ({found_slug})"
            results.append({
                "Company": name,
                "Industry": industry,
                "ATS": found_ats,
                "URL": found_url,
            })
        else:
            status = "✗ not found"
            not_found.append(name)

        print(f"[{i+1:3d}/{total}] {name:<45} {status}")
        time.sleep(0.1)

    # Deduplicate (some companies appear twice in seed list)
    seen_urls = set()
    deduped = []
    for r in results:
        if r["URL"] not in seen_urls:
            seen_urls.add(r["URL"])
            deduped.append(r)

    print(f"\n{'='*60}")
    print(f"RESULTS SUMMARY")
    print(f"{'='*60}")
    print(f"Total probed:      {total}")
    print(f"Found on GH/Ashby: {len(deduped)}")
    print(f"Not found:         {len(not_found)}")
    print(f"Hit rate:          {len(deduped)/total*100:.1f}%")

    gh = [r for r in deduped if r["ATS"] == "Greenhouse"]
    ashby = [r for r in deduped if r["ATS"] == "Ashby"]
    print(f"\nGreenhouse: {len(gh)}")
    print(f"Ashby:      {len(ashby)}")

    print(f"\nNot found on any ATS ({len(not_found)}):")
    for n in not_found:
        print(f"  - {n}")

    if write_csv:
        out_path = Path(__file__).parent / "job_boards.csv"
        with open(out_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=["Company", "Industry", "ATS", "URL"])
            writer.writeheader()
            writer.writerows(deduped)
        print(f"\n✓ Wrote {len(deduped)} companies to {out_path}")

    return deduped


if __name__ == "__main__":
    main()
