# Phase 2 data review

Total normalized records: **3392**

| List type | Count |
| --- | ---: |
| `want_list` | 997 |
| `have_list` | 1366 |
| `complete` | 1001 |
| `uncertain` | 28 |
| `needs_review` | 0 |

## Remaining human review

No unresolved normalization ambiguities detected.

## Applied human-reviewed decisions

- **1**: 1978 Burger King Tigers: 1218 → 12 18 (HAVE).
- **2**: 1976 Linnett Superstars Individual Cards: 107114 → 107 114.
- **3**: 1976 Towne Club Discs: remove accidental empty comma item.
- **4/9**: 2012 Topps ends at 424; discard appended duplicate 1993 heading/list.
- **5**: 1962 Play-Rite Roger Maris: owned example and Good enough note are valid.
- **6**: 1943 Grand Studio Milwaukee Brewers: remove accidental empty comma item.
- **7**: Carreras Film Stars 1937: set size 54, preserve HAVE 53.
- **8**: Gallaher Red Back 1934: total set size unknown, retain WANT 49 and 50.
- **10**: 2025 Topps Heritage: separate WANT record after Costco HAVE list.
- **11**: 2019 Topps Holiday (HW-): user-defined Complete, no wanted items.
- **12**: 2016 Milwaukee Brewers Team Set: listL → list:, separate HAVE MB-14.
- **13**: 2009 Bowman Chrome Prospects: 4748 → 47 48 (HAVE).
- **14**: 2008 Milwaukee Brewers Team Set: listL → list:, separate HAVE MIL10.
- **15**: 2006 Constitution SCC-: quote → colon, separate HAVE record.
- **16**: 2004 Upper Deck Power Up: 4750 → 47 50.
- **17**: 2001 Ritz/Oreo: WANT Blue Border Griffey, HAVE Red Border Griffey.
- **18**: 2000 Just Just Imagine: restore colon, separate WANT record.
- **19**: 1998 Fleer Sports Illustrated Opening Day: 2024 → 20 24.
- **20/21**: 1997 Leaf: 100104 → 100 104; one correction.
- **22**: 1988 Baseball Cards Magazine Replicards: remove empty comma item.
- **23**: 1987 Fleer Mini: 8991 → 89 91 (HAVE).

## Preserved uncertainty (not unresolved parser errors)

| Record | Source statement |
| --- | --- |
| `p0023-l001` 1980 Green Mountain Press American Folk Heroes | 1 (purportedly a 27 card set, though examples of anything besides card 1 seem difficult to find) |
| `p0060-l001` 1980 Unknown Manufacturer New York Yankees All-Time Greats | Believed to be complete |
| `p0239-l017` 1974 TCMA Sporting News — 1909 | Chas Adams, Baker, Carrigan, Cobb, Cobb/Wagner, Collins, Crawford, Harry Davis, Krause, McAleen, Mullin, Stahl, Wagner, Oversized Postcard of Pittsbugh Pirates team (Believe this to be complete) |
| `p0239-l018` 1974 TCMA Sporting News — 1910 | Barry, Brown, Evers, Johnson/Street, Konetchy, Leach, Lobert, Mack, McGraw, Merkle, Schulte, Snodgrass, Tinker, Oversized Postcard of Philadelphia Athletics team (Believe this to be complete) |
| `p0261-l003` 1973 TCMA Christmas Cards (possibly complete) | Santa/Wagner, Christmas Tree |
| `p0273-l029` 1972 (?) TCMA Nu Grape World Champion Athletics 1929 | Complete? (likely only one in set) |
| `p0273-l039` 1972-73 TCMA 1940 Team Composites (unconfirmed wantlist--availability is unknown) | Brooklyn, Chicago Cubs, Chicago White Sox, Cleveland, New York Giants, New York Yankees, Pittsburgh, Washington |
| `p0375-l001` 1963 Jay Publishing Milwaukee Braves | Bell, Coaches (Silvestri, Whatt, Bragan, Walker, White) (note: not in TCDB checklist--believed to be from 1963 as Bragan has cards in 1964 and 1965). |
| `p1809-l001` 1997 Collect-a-sport/College Division | Have Moonlight Graham. Likely one card set. |
| `p1996-l007` 1995 JSW — 33 Goudey Red Box | Aaron, Banks, Bench, Brock, Clemente, Cobb, Colavito, DiMaggio (portrait), Gehrig, Greenberg, J. Jackson, R. Jackson, Kaline, Killebrew, Mantle, Mays, Musial, Palmer, Ripken, F. Robinson, J. Robinson, Rose, Ruth (Red Sox), Ruth (Yanks), Ryan, Wagner, Yaz (possible missing: DiMaggio (with Monroe)) |
| `p1996-l008` 1995 JSW — 35 Goudey 4-in-1's in Blue, Red, and Yellow | Believe to be complete |
| `p1996-l009` 1995 JSW — 48 Bowman B&W | Aaron, Banks, Bench, Brock, Clemente, Cobb, Gehrig, Greenberg, J. Jackson, R. Jackson, Kaline, Killebrew, Mantle, Mays, Musial, Palmer, F. Robinson, J. Robinson, Rose, Ruth (Red Sox), Ruth (Yanks), Ryan, Yaz (possible missing: Colavito, DiMaggio (with Monroe), DiMaggio (Portrait), Ripken, Wagner) |
| `p1996-l010` 1995 JSW — 50 Bowman Black Border | DiMaggio (with Monroe), Gehrig, J. Jackson, Mays, Ripken, J. Robinson (Likely complete) |
| `p1996-l011` 1995 JSW — 50 Bowman Red Border | Aaron, Bench, Mantle, F. Robinson, Rose, Ryan (Likely complete) |
| `p1996-l012` 1995 JSW — 50 Bowman White Border | Aaron, Banks, Bench, Brock, Clemente, Colavito, DiMaggio (portrait), Gehrig, Greenberg, J. Jackson, R. Jackson, Killebrew, Mantle, Mays, Musial, Palmer, Ripken, F. Robinson, J. Robinson, Rose, Ruth (Red Sox), Ruth (Yanks), Ryan, Wagner, Yaz (Possible missing: Cobb, DiMaggio (with Monroe), Kaline) |
| `p1996-l013` 1995 JSW — 51 Bowman | DiMaggio (Joltin' Joe), Killebrew (The Killer), Koufax (the Great Lefty), Ruth (Yanks--Sultan of Swat), T. Williams (Splendid Splinter) Likely missing (could be more): Banks, Brock, Cobb, Greenberg, R. Jackson, Kaline, Musial, F. Robinson, Ryan, Wagner |
| `p1996-l014` 1995 JSW — 52 Bowman | Cobb (Georgia Peach), Killebrew (The Killer), Koufax (the Great Lefty), Musial (Stan the Man), Ruth (Yanks-the Bambino), T. Williams (Splendid Splinter). Likely missing (could be more): Banks, Bench, Clemente, DiMaggio, J. Jackson, R. Jackson, F. Robinson, J. Robinson, Ruth (Yanks--Sultan of Swat), Seaver, Wagner |
| `p1996-l015` 1995 JSW — 52 Topps | Aaron, Banks, Bench, Brock, Clemente, DiMaggio (portrait), Gehrig, Greenberg, R. Jackson, Ripken, F. Robinson, Rose, Ruth (Yanks-Sultan of Swat), Ryan, Yaz. (Possible missing (could be more): Cobb, DiMaggio (with Monroe), Kaline, Killebrew, Musial, Wagner, Williams) |
| `p1996-l016` 1995 JSW — 53 Bowman Black Box | Aaron, Banks, Brock, Clemente, DiMaggio (portrait), DiMaggio (with Monroe), Greenberg, R. Jackson, Palmer, Ripken, F. Robinson (Reds), J. Robinson, Ryan, Yaz (Possible missing (could be more): Kaline, F. Robinson (Orioles)) |
| `p1996-l017` 1995 JSW — 53 Bowman Script | Aaron, Banks, Bench, Brock, Clemente, DiMaggio (portrait), DiMaggio (with Monroe), J. Jackson, R. Jackson, Ripken, F. Robinson (Orioles), F. Robinson (Reds), J. Robinson, Rose, Yaz (possible missing (could be more): Colavito) |
| `p1996-l018` 1995 JSW — 53 Topps Black Box | Banks, Bench, Brock, Clemente, Greenberg, J. Jackson, R. Jackson, Koufax, Musial, Palmer, Ripken, F. Robinson (Reds), Ruth (Yanks--Sultan of Swat), Ryan, Yaz (possible missing (could be more): Cobb, Colavito, DiMaggio (portrait), DiMaggio (with Monroe), Gehrig, Kaline, Killebrew, Rose, Wagner) |
| `p1996-l019` 1995 JSW — 53 Topps Red Box | Banks, Bench, Clemente, R. Jackson, Killebrew, Koufax, Musial, Ruth (Yanks-Sultan of Swat), Seaver, T. Williams, Yaz. (Possible missing (could be more): Cobb, Kaline, Wagner) |
| `p1996-l020` 1995 JSW — 61 Topps | Bench, DiMaggio (portrait), DiMaggio (with Monroe), J. Jackson, Palmer, Ripken, J. Robinson, Rose. (possible missing (could be more): Cobb, Ryan, Wagner, Williams) |
| `p2501-l001` 1990(?) Negro Leagues Baseball Museum All Star Paige Postcard | Complete? |
| `p2529-l001` 1989 (ca.) Dairy Council of Wisconsin Milwaukee Brewers magnets (possibly complete) | Molitor, Plesac, Yount |
| `p2851-l007` 1985(?) Pacific Trading Cards Babe Ruth Postcard | Complete? |
| `p2887-l001` 1984 TCMA Baseball Advertiser Roberto Clemente FDC | Last Hit, World Series MVP (possibly complete?) |
| `p3022-l006` Baseball All-Time Greats (unsure of make--Green border) | Complete? Have cards 1-96. |

## Source fidelity and limitations

- WANT items are wanted; HAVE items are owned. No HAVE complements or external checklists were generated.
- Complete records have no listed cards/items. Upgrade and partial-completion wording remains in notes or mixed lists.
- Uncertain claims remain uncertain. Ranges remain source expressions; no endpoints or checklist sizes are guessed.
- Original DOCX, text, bold runs, and hyperlinks are retained. Paragraph/line references are one-based, including empty lines.
- The merged 2012/1993 text is paragraph 639 in this DOCX (the earlier review called it 638); correction matches wording.
- Football and baseball Topps records are separate, even when years and titles match.
- Category/brand labels are conservative search metadata; exact titles and source wording remain authoritative.
- Document context and broad collecting interests are retained in context_notes and the complete source ledger.
- This is a rebuild; the previous temporary scripts/tests were unavailable. Validation checks are recreated in tests/.
