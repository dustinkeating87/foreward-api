"""
Canonical course key → display name mapping for foreward-api.

alert_profiles.courses stores course keys (slug, e.g. "lakeview"). This module
is the write-time validation gate: any slug not present here is rejected 422.

Display names here must match what the scraper writes to sent_slots.course_name
(case-sensitive) for GolfNow and Chronogolf — authoritative source is
GOLFNOW_COURSES / CHRONOGOLF_COURSES in the scraper files.

GTG display names here are ADVISORY ONLY. The gateway API
(gateway.golfthe6ix.com) is the runtime authority; CourseName in live slots
may differ. Slugs are still canonical and must match exactly.

Keeping this dict in sync with the scraper's course registries is enforced by
CI (foreward-scraper/.github/workflows/check_course_keys.yml).
"""

from typing import Optional

# Ordered by platform. Keep in sync with the scraper's internal registries.
COURSES: dict[str, dict[str, str]] = {
    # ── GolfNow ──────────────────────────────────────────────────────────────
    "lakeview":          {"display_name": "Lakeview Golf Course",                      "platform": "golfnow"},
    "braeben":           {"display_name": "BraeBen Golf Course",                       "platform": "golfnow"},
    "eagles-nest":       {"display_name": "Eagles Nest Golf Club",                     "platform": "golfnow"},
    "royal-woodbine":    {"display_name": "Royal Woodbine Golf Club",                  "platform": "golfnow"},
    "angus-glen-north":  {"display_name": "Angus Glen Golf Club – North Course",  "platform": "golfnow"},
    "remington-valley":  {"display_name": "Remington Parkview – Valley Course",   "platform": "golfnow"},
    "remington-upper":   {"display_name": "Remington Parkview – Upper Course",    "platform": "golfnow"},
    "flemingdon-park":   {"display_name": "Flemingdon Park Golf Club",                 "platform": "golfnow"},
    "pickering-glen":    {"display_name": "Pickering Glen Golf Club",                  "platform": "golfnow"},
    "winchester":        {"display_name": "Winchester Golf Club",                      "platform": "golfnow"},
    "sandridge-dunes":   {"display_name": "Sandridge Dunes (Vero Beach, FL)",          "platform": "golfnow"},
    "sandridge-lakes":   {"display_name": "Sandridge Lakes (Vero Beach, FL)",          "platform": "golfnow"},
    # ── Chronogolf ───────────────────────────────────────────────────────────
    "osprey-heathlands": {"display_name": "TPC Toronto at Osprey Valley – Heathlands", "platform": "chronogolf"},
    "osprey-hoot":       {"display_name": "TPC Toronto at Osprey Valley – Hoot Course", "platform": "chronogolf"},
    "osprey-north":      {"display_name": "TPC Toronto at Osprey Valley – North Course", "platform": "chronogolf"},
    "royal-ashburn":     {"display_name": "Royal Ashburn Golf Club",                   "platform": "chronogolf"},
    "whispering-ridge":  {"display_name": "Whispering Ridge Golf Club",                "platform": "chronogolf"},
    "silver-lakes":      {"display_name": "Silver Lakes Golf & Country Club",          "platform": "chronogolf"},
    "bushwood":          {"display_name": "Bushwood Golf Club",                        "platform": "chronogolf"},
    # ── GTA verified 2026-09-29 (marketplace-resolved triples, live-probed) ────
    "deer-creek-golf-club-short-course-9-holes": {"display_name": "Deer Creek Golf Club - Short Course - 9 Holes", "platform": "golfnow"},
    "deer-creek-golf-club-north-course": {"display_name": "Deer Creek Golf Club North Course", "platform": "golfnow"},
    "deer-creek-golf-club-south-course": {"display_name": "Deer Creek Golf Club South Course", "platform": "golfnow"},
    "south-ajax-golf-club-lake-breeze": {"display_name": "South Ajax Golf Club - Lake Breeze", "platform": "golfnow"},
    "south-ajax-golf-club-whistling-wind": {"display_name": "South Ajax Golf Club - Whistling Wind", "platform": "golfnow"},
    "mystic-golf-club": {"display_name": "Mystic Golf Club", "platform": "golfnow"},
    "peel-village-golf-course-9-holes": {"display_name": "Peel Village Golf Course - 9 Holes", "platform": "golfnow"},
    "turnberry-golf-club-ontario": {"display_name": "Turnberry Golf Club - Ontario", "platform": "golfnow"},
    "hidden-lake-new-course": {"display_name": "Hidden Lake - New Course", "platform": "golfnow"},
    "hidden-lake-old-course": {"display_name": "Hidden Lake - Old Course", "platform": "golfnow"},
    "lowville-golf-club": {"display_name": "Lowville Golf Club", "platform": "golfnow"},
    "mount-nemo-golf-club": {"display_name": "Mount Nemo Golf Club", "platform": "golfnow"},
    "tyandaga-golf-course": {"display_name": "Tyandaga Golf Course", "platform": "golfnow"},
    "caistorville-golf-club": {"display_name": "Caistorville Golf Club", "platform": "golfnow"},
    "bantys-roost-golf-country-club": {"display_name": "Banty’s Roost Golf & Country Club", "platform": "golfnow"},
    "harbour-view-golf-country-club": {"display_name": "Harbour View Golf & Country Club", "platform": "golfnow"},
    "buncrana-golf-course-par-3": {"display_name": "Buncrana Golf Course - Par 3", "platform": "golfnow"},
    "dragons-fire-golf-club": {"display_name": "Dragon’s Fire Golf Club", "platform": "golfnow"},
    "east-wing-golf-course-cardinal-golf-club": {"display_name": "East Wing Golf Course - Cardinal Golf Club", "platform": "golfnow"},
    "kettle-creek-golf-course-cardinal-golf-club": {"display_name": "Kettle Creek Golf Course - Cardinal Golf Club", "platform": "golfnow"},
    "redcrest-golf-course-cardinal-golf-club": {"display_name": "RedCrest Golf Course - Cardinal Golf Club", "platform": "golfnow"},
    "west-wing-golf-course-cardinal-golf-club": {"display_name": "West Wing Golf Course - Cardinal Golf Club", "platform": "golfnow"},
    "braeben-golf-country-club-academy-course": {"display_name": "Braeben Golf & Country Club - Academy Course", "platform": "golfnow"},
    "goreway-golf-club": {"display_name": "Goreway Golf Club", "platform": "golfnow"},
    "southern-pines-golf-and-country-club": {"display_name": "Southern Pines Golf and Country Club", "platform": "golfnow"},
    "deerfield-golf-club-on": {"display_name": "Deerfield Golf Club (ON)", "platform": "golfnow"},
    "glen-abbey-golf-club": {"display_name": "Glen Abbey Golf Club", "platform": "golfnow"},
    "harmony-creek-golf-centre": {"display_name": "Harmony Creek Golf Centre", "platform": "golfnow"},
    "oshawa-airport-golf-club": {"display_name": "Oshawa Airport Golf Club", "platform": "golfnow"},
    "cherry-downs": {"display_name": "Cherry Downs", "platform": "golfnow"},
    "spring-creek-golf-club": {"display_name": "Spring Creek Golf Club", "platform": "golfnow"},
    "bloomington-downs-golf-club": {"display_name": "Bloomington Downs Golf Club", "platform": "golfnow"},
    "nobleton-lakes-golf-club": {"display_name": "Nobleton Lakes Golf Club", "platform": "golfnow"},
    "shawneeki-golf-club": {"display_name": "Shawneeki Golf Club", "platform": "golfnow"},
    "rolling-hills-bethesda-grange": {"display_name": "Rolling Hills - Bethesda Grange", "platform": "golfnow"},
    "royal-stouffville-executive": {"display_name": "Royal Stouffville Executive", "platform": "golfnow"},
    "royal-stouffville-golf-course": {"display_name": "Royal Stouffville Golf Course", "platform": "golfnow"},
    "foxbridge-golf-course": {"display_name": "Foxbridge Golf Course", "platform": "golfnow"},
    "mill-run-golf-club-highland-course": {"display_name": "Mill Run Golf Club - Highland Course", "platform": "golfnow"},
    "wooden-sticks-golf-club": {"display_name": "Wooden Sticks Golf Club", "platform": "golfnow"},
    "gull-river-golf-club": {"display_name": "Gull River Golf Club", "platform": "golfnow"},
    "uplands-golf-club": {"display_name": "Uplands Golf Club", "platform": "golfnow"},
    "oak-gables-golf-club-learning-centre": {"display_name": "Oak Gables Golf Club",                           "platform": "chronogolf"},
    "stonehenge-golf-club":                 {"display_name": "Stonehenge Golf Club",                            "platform": "chronogolf"},
    "parkshore-golf-club":                  {"display_name": "Goreway Golf Club",                               "platform": "chronogolf"},
    "banty-s-roost-golf-club":              {"display_name": "Banty’s Roost Golf Club",                         "platform": "chronogolf"},
    "carlisle-golf-country-club-north":     {"display_name": "Carlisle Golf & Country Club – North",            "platform": "chronogolf"},
    "cardinal-golf-club-redcrest":          {"display_name": "Cardinal Golf Complex – RedCrest",                "platform": "chronogolf"},
    "cardinal-golf-club-east-wing":         {"display_name": "Cardinal Golf Complex – East Wing",               "platform": "chronogolf"},
    "cardinal-golf-club-west-wing":         {"display_name": "Cardinal Golf Complex – West Wing",               "platform": "chronogolf"},
    "cardinal-golf-club-kettle-creek":      {"display_name": "Cardinal Golf Complex – Kettle Creek",            "platform": "chronogolf"},
    "kirbylinks-golf-course":               {"display_name": "Kirby Links Golf Course",                         "platform": "chronogolf"},
    "royal-ontario-golf-club":              {"display_name": "Royal Ontario Golf Club",                         "platform": "chronogolf"},
    "oshawa-golf-and-curling-club":         {"display_name": "Oshawa Golf Club",                                "platform": "chronogolf"},
    "summerlea-golf-club":                  {"display_name": "Summerlea Golf Club",                             "platform": "chronogolf"},
    "ballantrae-golf-club":                 {"display_name": "Ballantrae Golf Club",                            "platform": "chronogolf"},
    "mill-run-golf-club-ontario":           {"display_name": "Mill Run Golf Club",                              "platform": "chronogolf"},
    # ── Chronogolf / Muskoka (live-verified 2026-06-27) ─────────────────────────
    "muskoka-highlands":           {"display_name": "Muskoka Highlands Golf Links",  "platform": "chronogolf"},
    "the-fairways-at-kirrie-glen": {"display_name": "The Fairways at Kirrie Glen",   "platform": "chronogolf"},
    "diamond-in-the-ruff":         {"display_name": "Diamond in the Ruff",           "platform": "chronogolf"},
    # ── Tee-on ───────────────────────────────────────────────────────────────────
    # NS / HRM (live-verified 2026-06-13)
    "the-links-at-brunello":      {"display_name": "The Links at Brunello",             "platform": "teeon"},
    "airlane-golf-club":          {"display_name": "Airlane Golf Club",                 "platform": "teeon"},
    "fox-hollow-golf-club-ns":    {"display_name": "Fox Hollow Golf Club",              "platform": "teeon"},
    "indian-lake-golf-course":    {"display_name": "Indian Lake Golf Course",           "platform": "teeon"},
    "lost-creek-golf-club":       {"display_name": "Lost Creek Golf Club",              "platform": "teeon"},
    # Ontario / Toronto-area (live-verified 2026-06-13)
    "pheasant-run-golf-club":     {"display_name": "Pheasant Run Golf Club",            "platform": "teeon"},
    # Ontario / Hamilton-area (live-verified 2026-06-13)
    "granite-ridge-golf-club":    {"display_name": "Granite Ridge Golf Club",           "platform": "teeon"},
    "crosswinds-golf-country-club": {"display_name": "Crosswinds Golf & Country Club",  "platform": "teeon"},
    "willow-valley-golf-course":  {"display_name": "Willow Valley Golf Course",         "platform": "teeon"},
    # ── Chronogolf / NS Mainland (live-verified 2026-06-13) ──────────────────────
    "abercrombie-country-club-nova-scotia-new-glasgow": {"display_name": "Abercrombie Country Club",              "platform": "chronogolf"},
    "brookfield-golf-country-club":     {"display_name": "Brookfield Golf & Country Club",      "platform": "chronogolf"},
    "eagle-crest-golf-course-nova-scotia": {"display_name": "Eagle Crest Golf Course",          "platform": "chronogolf"},
    "eden-golf-and-country-club":       {"display_name": "Eden Golf and Country Club",          "platform": "chronogolf"},
    "greenwood-golf-club":              {"display_name": "Greenwood Golf Club",                 "platform": "chronogolf"},
    "truro-golf-club":                  {"display_name": "Truro Golf Club",                     "platform": "chronogolf"},
    "west-pubnico-golf-country-club-nova-scotia-pubnico": {"display_name": "West Pubnico Golf & Country Club", "platform": "chronogolf"},
    "antigonish-golf-country-club":     {"display_name": "Antigonish Golf & Country Club",      "platform": "chronogolf"},
    "white-point-golf-club":            {"display_name": "White Point Golf Club",               "platform": "chronogolf"},
    "northumberland-links":             {"display_name": "Northumberland Links",                 "platform": "chronogolf"},
    # ── Chronogolf / PEI (confirmed public tee times 2026-06-13) ─────────────────
    "eagles-glenn-golf-resort":         {"display_name": "Eagles Glenn Golf Resort",            "platform": "chronogolf"},
    "fox-meadow-golf-course":           {"display_name": "Fox Meadow Golf Course",              "platform": "chronogolf"},
    "mill-river-resort":                {"display_name": "Mill River Resort",                   "platform": "chronogolf"},
    "rustico-resort":                   {"display_name": "Rustico Resort",                      "platform": "chronogolf"},
    # ── GolfNow / NS (live-verified 2026-06-13) ──────────────────────────────────
    "ken-wo-golf-club":                 {"display_name": "Ken-Wo Golf Club",                    "platform": "golfnow"},
    "clare-golf-country-club":          {"display_name": "Clare Golf & Country Club",           "platform": "golfnow"},
    "river-hills-golf-ns":              {"display_name": "River Hills Golf & Country Club",     "platform": "golfnow"},
    # ── GTG (display names advisory — gateway API is authoritative at runtime) ─
    "dentonia-park":  {"display_name": "Dentonia Park Golf Course",  "platform": "gtg"},
    "don-valley":     {"display_name": "Don Valley Golf Course",     "platform": "gtg"},
    "humber-valley":  {"display_name": "Humber Valley Golf Course",  "platform": "gtg"},
    "maple-acres":    {"display_name": "Maple Acres Golf Course",    "platform": "gtg"},
    "scarlett-woods": {"display_name": "Scarlett Woods Golf Course", "platform": "gtg"},
    "tam-o-shanter":  {"display_name": "Tam O'Shanter Golf Course",  "platform": "gtg"},
    # ── Ontario expansion 2026-10-20 (live-probed through scraper request path) ──
    "lyndhurst-golf-course": {"display_name": "Lyndhurst Golf Course", "platform": "chronogolf"},
    "lakeview-house-golf-course": {"display_name": "Lakeview House Golf Course", "platform": "chronogolf"},
    "bushwood-golf-club-executive": {"display_name": "Bushwood Golf Club – Executive", "platform": "chronogolf"},
    "grand-valley-golf-country-club": {"display_name": "Grand Valley Golf & Country Club", "platform": "chronogolf"},
    "century-pines-golf-club": {"display_name": "Century Pines Golf Club", "platform": "chronogolf"},
    "puslinch-golf-club": {"display_name": "Puslinch Golf Club", "platform": "chronogolf"},
    "st-andrews-valley-golf-club": {"display_name": "St. Andrew's Valley Golf Club", "platform": "chronogolf"},
    "ariss-valley-golf-course-pines-willows": {"display_name": "Ariss Valley Golf Course – Pines/Willows", "platform": "chronogolf"},
    "ariss-valley-golf-course-willows-lakes": {"display_name": "Ariss Valley Golf Course – Willows/Lakes", "platform": "chronogolf"},
    "kitchener-golf-rockway": {"display_name": "Kitchener Golf – Rockway", "platform": "chronogolf"},
    "kitchener-golf-doon-valley": {"display_name": "Kitchener Golf – Doon Valley", "platform": "chronogolf"},
    "kitchener-golf-doon-valley-classic-9": {"display_name": "Kitchener Golf – Doon Valley Classic 9", "platform": "chronogolf"},
    "cedarhurst-golf-club": {"display_name": "Cedarhurst Golf Club", "platform": "chronogolf"},
    "lynbrook-family-golf-centre": {"display_name": "Lynbrook Family Golf Centre", "platform": "chronogolf"},
    "carlisle-golf-country-club-south": {"display_name": "Carlisle Golf & Country Club – South", "platform": "chronogolf"},
    "badlands-golf-company": {"display_name": "Badlands Golf Company", "platform": "chronogolf"},
    "westview-golf-club-homestead": {"display_name": "Westview Golf Club – Homestead", "platform": "chronogolf"},
    "westview-golf-club-middle": {"display_name": "Westview Golf Club – Middle", "platform": "chronogolf"},
    "silver-brooke-golf-club": {"display_name": "Silver Brooke Golf Club", "platform": "chronogolf"},
    "hockley-valley-resort": {"display_name": "Hockley Valley Resort", "platform": "chronogolf"},
    "cardinal-lakes-golf-club-heron": {"display_name": "Cardinal Lakes Golf Club – Heron", "platform": "chronogolf"},
    "olivers-nest-golf-club": {"display_name": "Oliver's Nest Golf Club", "platform": "chronogolf"},
    "chedoke-golf-club-martin": {"display_name": "Chedoke Golf Club – Martin", "platform": "chronogolf"},
    "chedoke-golf-club-beddoe": {"display_name": "Chedoke Golf Club – Beddoe", "platform": "chronogolf"},
    "kings-forest-golf-club": {"display_name": "King's Forest Golf Club", "platform": "chronogolf"},
    "big-bay-point-golf-and-country-club": {"display_name": "Big Bay Point Golf and Country Club", "platform": "chronogolf"},
    "newcastle-golf-and-country-club": {"display_name": "Newcastle Golf and Country Club", "platform": "chronogolf"},
    "dalewood-golf-club": {"display_name": "Dalewood Golf Club", "platform": "chronogolf"},
    "lionhead-golf-club-legends": {"display_name": "Lionhead Golf Club – Legends", "platform": "chronogolf"},
    "lionhead-golf-club-masters": {"display_name": "Lionhead Golf Club – Masters", "platform": "chronogolf"},
    "lakeridge-links-golf-club": {"display_name": "Lakeridge Links Golf Club", "platform": "chronogolf"},
    "woodington-lake-golf-club-the-lake-course": {"display_name": "Woodington Lake Golf Club – The Lake Course", "platform": "chronogolf"},
    "woodington-lake-golf-club-the-spire-course": {"display_name": "Woodington Lake Golf Club – The Spire Course", "platform": "chronogolf"},
    "the-nest-at-friday-harbour": {"display_name": "The Nest at Friday Harbour", "platform": "chronogolf"},
    "bunker-hill-golf-club": {"display_name": "Bunker Hill Golf Club", "platform": "chronogolf"},
    "niagara-on-the-lake-golf-club": {"display_name": "Niagara-on-the-Lake Golf Club", "platform": "chronogolf"},
    "acton-golf-club": {"display_name": "Acton Golf Club", "platform": "golfnow"},
    "hy-hope-farm-golf-course": {"display_name": "Hy-Hope Farm Golf Course", "platform": "golfnow"},
    "heritage-hills-golf-club": {"display_name": "Heritage Hills Golf Club", "platform": "golfnow"},
    "southbrook-golf-country-club": {"display_name": "Southbrook Golf & Country Club", "platform": "golfnow"},
    "brant-valley-golf-club": {"display_name": "Brant Valley Golf Club", "platform": "golfnow"},
    "burlington-springs-golf-and-country-club": {"display_name": "Burlington Springs Golf And Country Club", "platform": "golfnow"},
    "millcroft-golf-club": {"display_name": "Millcroft Golf Club", "platform": "golfnow"},
    "glen-eagle-golf-club": {"display_name": "Glen Eagle Golf Club", "platform": "golfnow"},
    "legacy-pines-golf-club": {"display_name": "Legacy Pines Golf Club", "platform": "golfnow"},
    "brookfield-golf-club": {"display_name": "Brookfield Golf Club", "platform": "golfnow"},
    "beaverdale-golf-club": {"display_name": "Beaverdale Golf Club", "platform": "golfnow"},
    "cambridge-golf-club": {"display_name": "Cambridge Golf Club", "platform": "golfnow"},
    "wildwinds-golf-links": {"display_name": "Wildwinds Golf Links", "platform": "golfnow"},
    "conestoga-golf-conference-centre": {"display_name": "Conestoga Golf & Conference Centre", "platform": "golfnow"},
    "flamborough-hills-golf-country-club": {"display_name": "Flamborough Hills Golf & Country Club", "platform": "golfnow"},
    "calerin-golf-club": {"display_name": "Calerin Golf Club", "platform": "golfnow"},
    "riverview-golf-club": {"display_name": "Riverview Golf Club", "platform": "golfnow"},
    "the-hawk-niagara-falls-golf-club": {"display_name": "The Hawk Niagara Falls Golf Club", "platform": "golfnow"},
    "pines-of-georgina": {"display_name": "Pines Of Georgina", "platform": "golfnow"},
    "hornby-glen-golf-course": {"display_name": "Hornby Glen Golf Course", "platform": "golfnow"},
    "riveredge-golf-club": {"display_name": "RiverEdge Golf Club", "platform": "golfnow"},
    "deer-run-golf-course-at-kawartha-lakes": {"display_name": "Deer Run Golf Course at Kawartha Lakes", "platform": "golfnow"},
    "dundee-golf-club": {"display_name": "Dundee Golf Club", "platform": "golfnow"},
    "chippawa-at-legends-on-the-niagara": {"display_name": "Chippawa at Legends on the Niagara", "platform": "golfnow"},
    "whirlpool-golf-course": {"display_name": "Whirlpool Golf Course", "platform": "golfnow"},
    "battlefield-at-legends-on-the-niagara": {"display_name": "Battlefield at Legends on the Niagara", "platform": "golfnow"},
    "usshers-creek-at-legends-on-the-niagara": {"display_name": "Ussher's Creek at Legends on the Niagara", "platform": "golfnow"},
    "thundering-waters-golf-club": {"display_name": "Thundering Waters Golf Club", "platform": "golfnow"},
    "beechwood-golf-club": {"display_name": "Beechwood Golf Club", "platform": "golfnow"},
    "rolling-meadows-golf-country-club": {"display_name": "Rolling Meadows Golf & Country Club", "platform": "golfnow"},
    "willodell-golf-club-of-niagara": {"display_name": "Willodell Golf Club Of Niagara", "platform": "golfnow"},
    "dufferin-glen-golf-club": {"display_name": "Dufferin Glen Golf Club", "platform": "golfnow"},
    "orangeville-golf-club": {"display_name": "Orangeville Golf Club", "platform": "golfnow"},
    "wolf-run-golf-club": {"display_name": "Wolf Run Golf Club", "platform": "golfnow"},
    "the-oaks-of-st-george-golf-club": {"display_name": "The Oaks of St. George Golf Club", "platform": "golfnow"},
    "black-diamond-golf-club": {"display_name": "Black Diamond Golf Club", "platform": "golfnow"},
    "ash-brook-golf-club": {"display_name": "Ash Brook Golf Club", "platform": "golfnow"},
    "richmond-hill-golf-club": {"display_name": "Richmond Hill Golf Club", "platform": "golfnow"},
    "rockway-vineyards-golf-course": {"display_name": "Rockway Vineyards Golf Course", "platform": "golfnow"},
    "grand-niagara-golf-club": {"display_name": "Grand Niagara Golf Club", "platform": "golfnow"},
    "angus-glen-golf-club-south-course": {"display_name": "Angus Glen Golf Club – South Course", "platform": "golfnow"},
    "water-park-golf-country-club": {"display_name": "Water Park Golf & Country Club", "platform": "golfnow"},
    "grey-silo-golf-club": {"display_name": "Grey Silo Golf Club", "platform": "golfnow"},
    # ── Tee-on Ontario expansion 2026-10-20 ──
    "4-seasons-country-club": {"display_name": "4 Seasons Country Club", "platform": "teeon"},
    "baxter-creek-golf-club": {"display_name": "Baxter Creek Golf Club", "platform": "teeon"},
    "bear-creek-golf-club-barrie": {"display_name": "Bear Creek Golf Club (Barrie)", "platform": "teeon"},
    "beeton-golf-country-club": {"display_name": "Beeton Golf & Country Club", "platform": "teeon"},
    "big-cedar-point-golf-country-club": {"display_name": "Big Cedar Point Golf & Country Club", "platform": "teeon"},
    "brock-golf-course": {"display_name": "Brock Golf Course", "platform": "teeon"},
    "centennial-park-golf-centre": {"display_name": "Centennial Park Golf Centre", "platform": "teeon"},
    "chippewa-creek-golf-course": {"display_name": "Chippewa Creek Golf Course", "platform": "teeon"},
    "crestwood-golf-club": {"display_name": "Crestwood Golf Club", "platform": "teeon"},
    "elmira-golf-club": {"display_name": "Elmira Golf Club", "platform": "teeon"},
    "fescues-edge-golf-club": {"display_name": "Fescue's Edge Golf Club", "platform": "teeon"},
    "fort-erie-golf-club": {"display_name": "Fort Erie Golf Club", "platform": "teeon"},
    "freedom-oaks-golf-club": {"display_name": "Freedom Oaks Golf Club", "platform": "teeon"},
    "lindsay-golf-country-club": {"display_name": "Lindsay Golf & Country Club", "platform": "teeon"},
    "lyndebrook-golf-course": {"display_name": "Lyndebrook Golf Course", "platform": "teeon"},
    "orchard-beach-golf-country-club": {"display_name": "Orchard Beach Golf & Country Club", "platform": "teeon"},
    "pebblestone-golf-course": {"display_name": "Pebblestone Golf Course", "platform": "teeon"},
    "pineland-greens-golf-club": {"display_name": "Pineland Greens Golf Club", "platform": "teeon"},
    "port-hope-golf-country-club": {"display_name": "Port Hope Golf & Country Club", "platform": "teeon"},
    "queenston-golf-club": {"display_name": "Queenston Golf Club", "platform": "teeon"},
    "savannah-golf-links": {"display_name": "Savannah Golf Links", "platform": "teeon"},
    "sawmill-golf-course": {"display_name": "Sawmill Golf Course", "platform": "teeon"},
    "shanty-bay-golf-club": {"display_name": "Shanty Bay Golf Club", "platform": "teeon"},
    "shelburne-golf-country-club": {"display_name": "Shelburne Golf & Country Club", "platform": "teeon"},
    "simoro-golf-links": {"display_name": "Simoro Golf Links", "platform": "teeon"},
    "springfield-golf-country-club": {"display_name": "Springfield Golf & Country Club", "platform": "teeon"},
    "springwater-golf-course": {"display_name": "Springwater Golf Course", "platform": "teeon"},
    "st-davids-golf-club": {"display_name": "St. Davids Golf Club", "platform": "teeon"},
    "sunnybrae-golf-club": {"display_name": "Sunnybrae Golf Club", "platform": "teeon"},
    "the-wilds-at-cedar-valley-golf-course": {"display_name": "The Wilds at Cedar Valley Golf Course", "platform": "teeon"},
    "twenty-valley-golf-country-club": {"display_name": "Twenty Valley Golf & Country Club", "platform": "teeon"},
    "valleymede-columbus-golf-club": {"display_name": "Valleymede Columbus Golf Club", "platform": "teeon"},
    "victoria-park-east-golf-club": {"display_name": "Victoria Park East Golf Club", "platform": "teeon"},
    "victoria-park-valley-golf-club": {"display_name": "Victoria Park Valley Golf Club", "platform": "teeon"},
}


def display_name(key: str) -> str:
    """Return display name for a course key, or the key itself if unknown."""
    entry = COURSES.get(key)
    return entry["display_name"] if entry else key


def course_platform(key: str) -> Optional[str]:
    """Return platform for a course key, or None if unknown."""
    entry = COURSES.get(key)
    return entry["platform"] if entry else None


def all_keys() -> list[str]:
    """All known course keys."""
    return list(COURSES.keys())


def all_courses() -> list[dict]:
    """All courses as {key, display_name, platform} dicts."""
    return [
        {"key": k, "display_name": v["display_name"], "platform": v["platform"]}
        for k, v in COURSES.items()
    ]
