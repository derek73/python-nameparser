"""The ctgov-officials and ctgov-contacts local corpora: ClinicalTrials.gov's
study officials and site contacts.

ctgov-officials -- every overall official of every study on
ClinicalTrials.gov, whatever the role (principal investigators, study
directors and chairs, and a few sub-investigators and officials with no
role), the name as the sponsor's staff typed it into a free-text field,
with credentials, job titles and typos left in, each with its study, its
role and a country: the ISO 3166-1 alpha-2 code of the one country every
site of the study is in, and "" where the sites are in several countries,
a site states none, or the study lists no site. The country says where
the study ran, not where the official is from; the affiliation text is
not read (#1451).

ctgov-contacts -- the named contacts under each study's sites, the
officials' sibling (#1451): one record per contact name, role, study and
site country, a name listed again with the same role at another site of
one study in one country kept once and counted, each with its role
(mostly CONTACT, PRINCIPAL_INVESTIGATOR or SUB_INVESTIGATOR, as the
registry writes it) and its site's country code,
"" where the site states no country. Central contacts are left out: they
belong to no site, so they have no country of their own. A corpus of its
own rather than more records in ctgov-officials, so the counts already
quoted from that one stay true.

Both are fetched from API v2 (NLM), each paging the whole registry, and
the registry's country names (`Turkey (Türkiye)`, `South Korea`) are
mapped to codes by CTGOV_COUNTRIES, so the groups line up with
orcid-researchers' and patentsview-inventors'; a name the map does not
hold fails the fetch, naming it. ClinicalTrials.gov's terms ask anyone
redistributing the data to credit it, show NLM's processing date and say
what was changed: every report local_corpora.py prints and the
tools/name_usage.py row carry the credit and the date, the names are
kept unchanged; the changes are the country, a code for the registry's
name, and ctgov-contacts' repeats, kept once.
"""
from __future__ import annotations

import sys
import urllib.parse
from collections import Counter
from collections.abc import Callable, Iterator
from typing import Any

from local_core import Fetched, _get_json, _pinned, _refuse_past


CTGOV_API = "https://clinicaltrials.gov/api/v2"
CTGOV_PAGE = 1000  # the API's largest page
CTGOV_OFFICIALS = "ctgov-officials"
CTGOV_CONTACTS = "ctgov-contacts"
#: LocationCountry alone still returns a site stating no country, as
#: {} (NCT00320424, 2026-11-18), so the rule sees it.
OFFICIAL_FIELDS = "NCTId,OverallOfficialName,OverallOfficialRole,LocationCountry"
CONTACT_FIELDS = "NCTId,LocationCountry,LocationContactName,LocationContactRole"
#: The version of how a record is built from what the API gives (the
#: country rule, ctgov-contacts' repeat key and CTGOV_COUNTRIES's
#: codes), stored in meta.json and
#: required on load: bump it with any change to any of them, so a corpus read
#: the old way is refused rather than read. 1: the country (#1451); a
#: corpus fetched before it holds no "country" and is refused too.
CTGOV_READ_VERSION = 1
#: The most of the officials kept whose study lists no site, and of the
#: officials or contacts kept at a site stating no country, before a
#: fetch is refused: a renamed "locations" or "country" key would
#: otherwise empty every record's country in silence. Measured
#: 2026-11-18 by the API's own filters: of the 430,126 studies naming an
#: official, 31,924 list no site country, all but 15 of them no site at
#: all (about 7.4%), and no site of 3,000 studies paged stated no
#: country.
CTGOV_MAX_NO_SITE = 0.25
CTGOV_MAX_COUNTRYLESS = 0.01

#: Every country name the registry writes, as listed by
#: /api/v2/stats/field/values?fields=LocationCountry (226 names on
#: 2026-11-18), with its ISO 3166-1 alpha-2 code. A territory the
#: registry names apart (Puerto Rico, Guam, Réunion) keeps its own code,
#: as ISO gives it one (Reunion: RE). Four names have no current code: Kosovo takes the
#: user-assigned XK, the code in common use for it, and Serbia and Montenegro, the
#: Federal Republic of Yugoslavia and the Netherlands Antilles their
#: former codes (CS, YU, AN, ISO 3166-3). Names are looked up with their
#: edges stripped: the registry writes one with a trailing space.
CTGOV_COUNTRIES: dict[str, str] = {
    "Afghanistan": "AF", "Aland Islands": "AX", "Albania": "AL", "Algeria": "DZ",
    "American Samoa": "AS", "Andorra": "AD", "Angola": "AO", "Anguilla": "AI",
    "Antarctica": "AQ", "Antigua and Barbuda": "AG", "Argentina": "AR",
    "Armenia": "AM", "Aruba": "AW", "Australia": "AU", "Austria": "AT",
    "Azerbaijan": "AZ", "Bahrain": "BH", "Bangladesh": "BD", "Barbados": "BB",
    "Belarus": "BY", "Belgium": "BE", "Belize": "BZ", "Benin": "BJ",
    "Bermuda": "BM", "Bhutan": "BT", "Bolivia": "BO",
    "Bonaire, Saint Eustatius and Saba": "BQ", "Bosnia and Herzegovina": "BA",
    "Botswana": "BW", "Brazil": "BR", "Brunei": "BN", "Bulgaria": "BG",
    "Burkina Faso": "BF", "Burma": "MM", "Burundi": "BI", "Cabo Verde": "CV",
    "Cambodia": "KH", "Cameroon": "CM", "Canada": "CA", "Cayman Islands": "KY",
    "Central African Republic": "CF", "Chad": "TD", "Chile": "CL", "China": "CN",
    "Christmas Island": "CX", "Colombia": "CO", "Comoros": "KM",
    "Costa Rica": "CR", "Côte d’Ivoire": "CI", "Croatia": "HR", "Cuba": "CU",
    "Curacao": "CW", "Cyprus": "CY", "Czechia": "CZ",
    "Democratic Republic of the Congo": "CD", "Denmark": "DK", "Djibouti": "DJ",
    "Dominica": "DM", "Dominican Republic": "DO", "Ecuador": "EC", "Egypt": "EG",
    "El Salvador": "SV", "Equatorial Guinea": "GQ", "Eritrea": "ER",
    "Estonia": "EE", "Eswatini": "SZ", "Ethiopia": "ET", "Faroe Islands": "FO",
    "Federal Republic of Yugoslavia": "YU", "Fiji": "FJ", "Finland": "FI",
    "France": "FR", "French Guiana": "GF", "French Polynesia": "PF",
    "French Southern and Antarctic Lands": "TF", "Gabon": "GA", "Georgia": "GE",
    "Germany": "DE", "Ghana": "GH", "Gibraltar": "GI", "Greece": "GR",
    "Greenland": "GL", "Grenada": "GD", "Guadeloupe": "GP", "Guam": "GU",
    "Guatemala": "GT", "Guinea": "GN", "Guinea-Bissau": "GW", "Guyana": "GY",
    "Haiti": "HT", "Holy See": "VA", "Honduras": "HN", "Hong Kong": "HK",
    "Hungary": "HU", "Iceland": "IS", "India": "IN", "Indonesia": "ID",
    "Iran": "IR", "Iraq": "IQ", "Ireland": "IE", "Israel": "IL", "Italy": "IT",
    "Jamaica": "JM", "Japan": "JP", "Jersey": "JE", "Jordan": "JO",
    "Kazakhstan": "KZ", "Kenya": "KE", "Kiribati": "KI", "Kosovo": "XK",
    "Kuwait": "KW", "Kyrgyzstan": "KG", "Laos": "LA", "Latvia": "LV",
    "Lebanon": "LB", "Lesotho": "LS", "Liberia": "LR", "Libya": "LY",
    "Liechtenstein": "LI", "Lithuania": "LT", "Luxembourg": "LU", "Macau": "MO",
    "Madagascar": "MG", "Malawi": "MW", "Malaysia": "MY", "Maldives": "MV",
    "Mali": "ML", "Malta": "MT", "Martinique": "MQ", "Mauritania": "MR",
    "Mauritius": "MU", "Mayotte": "YT", "Mexico": "MX", "Micronesia": "FM",
    "Moldova": "MD", "Monaco": "MC", "Mongolia": "MN", "Montenegro": "ME",
    "Montserrat": "MS", "Morocco": "MA", "Mozambique": "MZ", "Namibia": "NA",
    "Nepal": "NP", "Netherlands": "NL", "Netherlands Antilles": "AN",
    "New Caledonia": "NC", "New Zealand": "NZ", "Nicaragua": "NI", "Niger": "NE",
    "Nigeria": "NG", "Niue": "NU", "North Korea": "KP", "North Macedonia": "MK",
    "Northern Mariana Islands": "MP", "Norway": "NO", "Oman": "OM",
    "Pakistan": "PK", "Palestinian Territories": "PS", "Panama": "PA",
    "Papua New Guinea": "PG", "Paraguay": "PY", "Peru": "PE",
    "Philippines": "PH", "Poland": "PL", "Portugal": "PT", "Puerto Rico": "PR",
    "Qatar": "QA", "Republic of the Congo": "CG", "Reunion": "RE",
    "Romania": "RO", "Russia": "RU", "Rwanda": "RW", "Saint Kitts and Nevis": "KN",
    "Saint Lucia": "LC", "Saint Martin": "MF",
    "Saint Vincent and the Grenadines": "VC", "Samoa": "WS", "San Marino": "SM",
    "Saudi Arabia": "SA", "Senegal": "SN", "Serbia": "RS",
    "Serbia and Montenegro": "CS", "Seychelles": "SC", "Sierra Leone": "SL",
    "Singapore": "SG", "Slovakia": "SK", "Slovenia": "SI",
    "Solomon Islands": "SB", "Somalia": "SO", "South Africa": "ZA",
    "South Korea": "KR", "South Sudan": "SS", "Spain": "ES", "Sri Lanka": "LK",
    "Sudan": "SD", "Suriname": "SR", "Sweden": "SE", "Switzerland": "CH",
    "Syria": "SY", "Taiwan": "TW", "Tajikistan": "TJ", "Tanzania": "TZ",
    "Thailand": "TH", "The Bahamas": "BS", "The Gambia": "GM",
    "Timor-Leste": "TL", "Togo": "TG", "Trinidad and Tobago": "TT",
    "Tunisia": "TN", "Turkey (Türkiye)": "TR", "Turkmenistan": "TM",
    "Uganda": "UG", "Ukraine": "UA", "United Arab Emirates": "AE",
    "United Kingdom": "GB", "United States": "US",
    "United States Minor Outlying Islands": "UM", "Uruguay": "UY",
    "Uzbekistan": "UZ", "Vanuatu": "VU", "Venezuela": "VE", "Vietnam": "VN",
    "Virgin Islands": "VI", "Yemen": "YE", "Zambia": "ZM", "Zimbabwe": "ZW",
}


def country_code(name: str, nct: str) -> str:
    """The ISO code of the registry's country `name` (CTGOV_COUNTRIES),
    or ValueError naming it and the study `nct` that wrote it: an
    unmapped name would otherwise read as no country."""
    code = CTGOV_COUNTRIES.get(name.strip())
    if code is None:
        raise ValueError(f"{nct} lists a site in {name!r}, which "
                         f"local_ctgov.CTGOV_COUNTRIES does not map to an ISO "
                         f"code; add it and fetch again")
    return code


def _ctgov_version() -> tuple[str, str]:
    data = _get_json(f"{CTGOV_API}/version")
    return str(data["dataTimestamp"]), str(data["apiVersion"])


def _ctgov_pages(fields: str) -> Iterator[dict[str, Any]]:
    token = ""
    while True:
        query = {"pageSize": CTGOV_PAGE, "fields": fields}
        if token:
            query["pageToken"] = token
        else:
            query["countTotal"] = "true"
        page = _get_json(f"{CTGOV_API}/studies?{urllib.parse.urlencode(query)}")
        yield page
        token = page.get("nextPageToken", "")
        if not token:
            return


def _ctgov_read(fields: str, take: Callable[[str, dict[str, Any]], None]
                ) -> tuple[str, str, int]:
    """Page the registry for `fields`, handing each study's NCT id and
    contactsLocationsModule to `take`, and return the data date, the API
    version and the studies paged.

    The registry is refreshed daily, so the data date is read before and
    after: a fetch that straddles a refresh mixes two days and is
    refused. A study paged twice is refused, since its names would count
    twice, and the studies paged must number the totalCount the first
    page states, so a fetch cut short cannot pass for the registry."""
    before, api = _ctgov_version()
    total: int | None = None
    studies: set[str] = set()
    for number, page in enumerate(_ctgov_pages(fields), 1):
        if total is None:
            total = int(page["totalCount"])
        if number % 50 == 0:
            print(f"  {len(studies):,} of {total:,} studies", file=sys.stderr)
        for study in page["studies"]:
            section = study["protocolSection"]
            nct = section["identificationModule"]["nctId"]
            if nct in studies:
                raise ValueError(f"{nct} was paged twice: the pages shifted "
                                 f"under the fetch; fetch again")
            studies.add(nct)
            take(nct, section.get("contactsLocationsModule", {}))
    after, _ = _ctgov_version()
    if after != before:
        raise ValueError(f"ClinicalTrials.gov refreshed during the fetch "
                         f"({before} -> {after}); fetch again")
    if len(studies) != total:
        raise ValueError(f"paged {len(studies):,} studies of the "
                         f"{total:,} the API counted; fetch again")
    return before, api, total


def _site_country(site: dict[str, Any], nct: str) -> str:
    """A site's country code, or "" where it states no country; a
    country that is not text, or that CTGOV_COUNTRIES does not map,
    raises ValueError naming the study."""
    name = site.get("country")
    if name is None:
        return ""
    if not isinstance(name, str):
        raise ValueError(f"{nct} lists a site whose country is {name!r}, not "
                         f"text: the API's shape has changed")
    return country_code(name, nct) if name.strip() else ""


def _role(entry: dict[str, Any], nct: str) -> str:
    """An official's or contact's role, "" where it states none; a role
    that is not text raises, naming the study, rather than writing a
    corpus every reader refuses."""
    role = entry.get("role", "")
    if not isinstance(role, str):
        raise ValueError(f"{nct} lists a role {role!r}, not text: the API's "
                         f"shape has changed")
    return role


def _gated(records: list[dict[str, str]], counted: list[tuple[int, float, str]]) -> None:
    """Refuse a fetch whose records hold no country at all, or where any
    of `counted`'s (count, share, what) is past its share of the records
    (CTGOV_MAX_NO_SITE, CTGOV_MAX_COUNTRYLESS)."""
    if records and not any(r["country"] for r in records):
        raise ValueError(f"none of {len(records):,} records holds a country: "
                         f"a location's \"country\" key may have moved")
    _refuse_past([(count, len(records), share, what) for count, share, what in counted],
                 "a location's key may have moved")


def fetch_ctgov() -> Fetched:
    """Every study's overall officials, in the API's order, each with
    the country its study's sites share (the module docstring).

    An official with no name is counted rather than dropped in silence,
    so a renamed field shows as a count in meta.json's detail, which
    `fetch` prints, instead of a smaller registry; the officials kept are
    counted there by where their study's sites are: none listed, then
    a site stating none (whatever the other sites say), then several
    countries, else one. A fetch past CTGOV_MAX_NO_SITE or
    CTGOV_MAX_COUNTRYLESS, or holding no country at all, is refused."""
    records: list[dict[str, str]] = []
    nameless = 0
    sites: Counter[str] = Counter()

    def take(nct: str, module: dict[str, Any]) -> None:
        nonlocal nameless
        codes = [_site_country(site, nct) for site in module.get("locations", [])]
        named = set(codes) - {""}
        if not codes:
            where, country = "no_site", ""
        elif "" in codes:
            where, country = "a_site_without_a_country", ""
        elif len(named) > 1:
            where, country = "several_countries", ""
        else:
            where, country = "one_country", named.pop()
        for official in module.get("overallOfficials", []):
            if official.get("name"):
                records.append({"name": official["name"], "study": nct,
                                "role": _role(official, nct), "country": country})
                sites[where] += 1
            else:
                nameless += 1

    date, api, total = _ctgov_read(OFFICIAL_FIELDS, take)
    _gated(records, [
        (sites["no_site"], CTGOV_MAX_NO_SITE, "officials of a study listing no site"),
        (sites["a_site_without_a_country"], CTGOV_MAX_COUNTRYLESS,
         "officials of a study with a site stating no country")])
    return Fetched(records, date, {
        "api_version": api, "studies": total, "read_version": CTGOV_READ_VERSION,
        "officials_without_a_name": nameless,
        "officials_by_sites": dict(sorted(sites.items()))})


def fetch_ctgov_contacts() -> Fetched:
    """Every named contact under every study's sites, in the API's
    order, once per name, role, study and country (the module
    docstring), counting in meta.json's detail the contacts without a
    name, the repeats dropped and the records kept at a site stating no
    country. A fetch past CTGOV_MAX_COUNTRYLESS, or holding no country
    at all, is refused."""
    records: list[dict[str, str]] = []
    nameless = repeated = countryless = 0

    def take(nct: str, module: dict[str, Any]) -> None:
        nonlocal nameless, repeated, countryless
        seen: set[tuple[str, str, str]] = set()
        for site in module.get("locations", []):
            country = _site_country(site, nct)
            for contact in site.get("contacts", []):
                name = contact.get("name")
                if not name:
                    nameless += 1
                    continue
                role = _role(contact, nct)
                if (name, role, country) in seen:
                    repeated += 1
                    continue
                seen.add((name, role, country))
                countryless += not country
                records.append({"name": name, "study": nct, "role": role,
                                "country": country})

    date, api, total = _ctgov_read(CONTACT_FIELDS, take)
    _gated(records, [(countryless, CTGOV_MAX_COUNTRYLESS,
                      "contacts at a site stating no country")])
    return Fetched(records, date, {
        "api_version": api, "studies": total, "read_version": CTGOV_READ_VERSION,
        "contacts_without_a_name": nameless,
        "repeated_in_study_and_country": repeated,
        "at_a_site_without_a_country": countryless})


#: Source.check for both corpora: a corpus read by another
#: CTGOV_READ_VERSION, or fetched before there was one (and so without a
#: "country"), is refused, naming the fetch that replaces it.
check_ctgov = _pinned("read_version", lambda: CTGOV_READ_VERSION,
                      "was read by read version {held}, and this tool reads "
                      "version {wanted}")
