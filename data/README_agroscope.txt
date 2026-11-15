This readme file was generated on 2025-07-25 by Nathalie Wuyts


GENERAL INFORMATION

Title of Dataset: Winter wheat performance data for varieties grown under low input conditions in Switzerland over the period 1990-2023, together with trial site weather data and variety genetic marker data

Author/Principal Investigator Information
Name: Lilia Levy Häner
ORCID: 0009-0009-2019-9241
Institution: AGROSCOPE
Address: Route de Duillier 60, 1260 Nyon, Switzerland
Email: lilia.levy@agroscope.admin.ch

Author/Associate or Co-investigator Information
Name: Juan M. Herrera
ORCID: 0000-0002-9398-7224
Institution: AGROSCOPE
Address: Route de Duillier 60, 1260 Nyon, Switzerland
Email: juan.herrera@agroscope.admin.ch

Author/Alternate Contact Information
Name: Nathalie Wuyts
ORCID: 0000-0002-4445-507X
Institution: AGROSCOPE
Address: Route de Duillier 60, 1260 Nyon, Switzerland
Email: nathalie.wuyts@agroscope.admin.ch

Date of data collection: 1990-2023 

Geographic location of data collection: Swiss wheat production zone (from Western to Eastern Switzerland, between 390 and 640 m.a.s.l.).

Information about funding sources that supported the collection of the data: Official Swiss variety testing (VCU) is supported by the Swiss Federal Office for Agriculture (https://www.blw.admin.ch/) and swiss granum (https://www.swissgranum.ch/).


SHARING/ACCESS INFORMATION

Licenses/restrictions placed on the data: Creative commons attribution 4.0 international 

Links to publications that cite or use the data: to be added upon publication

Links to other publicly accessible locations of the data: n/a (not applicable)

Links/relationships to ancillary data sets: n/a

Was data derived from another source? no
If yes, list source(s): 

Recommended citation for this dataset: 
	Levy Häner L., Strebel S., Visse-Mansiaux M., Wuyts N., Herrera J.M. and Pellet D. (2025). 
	Winter wheat performance data for varieties grown under low input conditions in Switzerland 
	over the period 1990-2023, together with trial site weather data and variety genetic marker data. Version 1.0.0. 
	10.5281/zenodo.16420898


DATA & FILE OVERVIEW

File List:
1. "yield_v1.0.0.csv", winter wheat grain yield expressed in dt per ha (15% moisture content) collected in a range of years (1990-2023) and locations (anonymized, L1-L16) for a set of varieties (Swiss and foreign varieties, anonymized, V1-V98).
2. "proteinContent_v1.0.0.csv", winter wheat grain protein content expressed in % collected in a range of years (1990-2023) and locations (anonymized, L1-L16) for a set of varieties (Swiss and foreign varieties, anonymized, V1-V98).
3. "weatherVariables_v1.0.0.csv", weather data for the range of years (1990-2023) and locations (anonymized, L1-L16), from which wheat yield and grain protein content data were obtained.
4. "weatherVariables_units_v1.0.0.csv", description and corresponding units and time periods for the weather variables in the file "weatherVariables_v1.0.0.csv".
5. "SNP_v1.0.0.csv", single nucleotide polymorphism (SNP) marker data for the set of varieties (Swiss and foreign varieties, anonymized, V1-V98), for which wheat yield and grain protein content data were obtained.

Relationship between files, if important: 
- years (1990-2023), growing locations (L1-L16) and varieties (V1-V98) correspond between the yield and grain protein content data, and with the weather variable data and SNP data, respectively.
- the file "weatherVariables_units_v1.0.0.csv" provides metadata for the interpretation of the weather variable data in the file "weatherVariables_v1.0.0.csv".

Additional related data collected that was not included in the current data package: further agronomical data and data related to the quality of derived wheat flour (see Strebel et al., 2025).

Strebel S., Levy Häner L., Imhoff Y., Watroba M., Girard M., Yerly R., Jaunin V., Grandgirard R., Pünter C., Linder N. and Weisflog T. (2025). Liste der empfohlenen Getreidesorten für die Ernte 2026. 
Agroscope Transfer, 591. https://link.ira.agroscope.ch/en-US/publication/59585

Are there multiple versions of the dataset? no
If yes, name of file(s) that was updated: 
Why was the file updated? 
When was the file updated? 


METHODOLOGICAL INFORMATION

Description of methods used for collection/generation of data: data were collected in the frame of official Swiss variety trials that test winter wheat varieties for their cultivation and use (VCU) in multiple locations in Switzerland. 

Methods for processing the data: locations where winter wheat was grown were anonymized using a letter (L) + number (1-16) code; variety names where anonymized using a letter (V) + number (1-98) code.

Instrument- or software-specific information needed to interpret the data: n/a

Standards and calibration information, if appropriate: n/a

Environmental/experimental conditions: 

The locations of the multi-environment trials spanned the Swiss wheat production zone (from Western to Eastern Switzerland, between 390 and 640 m.a.s.l.). 
Field trials were set up in a lattice design with three repetitions (plots) per variety. Sowing was done in October-November, depending on weather and field conditions, at a rate of 350-450 grains per m2. 
Plots measured 7.5 ± 0.9 m2 (1.5 m × 5 m) and were harvested per location using a combine harvester when the latest variety had a grain moisture content below 15% (in June-July). 
The data were collected under low input conditions, which means that no plant growth regulators or pesticides were applied, and herbicides only as needed. 
Fertilizer treatments consisted of 140 kg nitrogen per ha, modified based on local practices and according to the “Principles of fertilization of agricultural crops in Switzerland” (Richner & Sinaj, 2017). 
Inorganic nitrogen fertilizer was split into two or three applications. Irrigation was used only in very exceptional drought conditions between flowering and harvest.

Richner W. & Sinaj S., 2017. Grundlagen für die Düngung landwirtschaftlicher Kulturen in der Schweiz (GRUD 2017). Agrarforschung Schweiz 8, Spezialpublikation, 276 S. 
https://www.agrarforschungschweiz.ch/2017/06/grundlagen-fuer-die-duengung-landwirtschaftlicher-kulturen-in-der-schweiz-grud-2017

Describe any quality-assurance procedures performed on the data: the metadata were curated to ensure that the names of varieties and locations were correct across datasets.

People involved with sample collection, processing, analysis and/or submission: n/a


DATA-SPECIFIC INFORMATION FOR: "yield_v1.0.0.csv"

Number of variables: 5

Number of cases/rows: 11609

Variable List:

1. year: year in which the wheat trial was harvested, unitless.				
2. location_code: code indicating a unique location in anonymized form, consisting of the letter "L" followed by a number, unitless, the range is L1 to L16.
3. variety_code: code indicating a unique variety in anonymized form, consisting of the letter "V" followed by a number, unitless, the range is V1 to V98.
4. repetition: number indicating the plot repetition number per variety and trial location, unitless.
5. yield_dtPerHa: wheat grain yield at 15% moisture content, dt per ha.

Missing data codes: NA, not available

Specialized formats or other abbreviations used: n/a


DATA-SPECIFIC INFORMATION FOR: "proteinContent_v1.0.0.csv"

Number of variables: 4

Number of cases/rows: 3667

Variable List:

1. year: year in which the wheat trial was harvested, unitless.				
2. location_code: code indicating a unique location in anonymized form, consisting of the letter "L" followed by a number, unitless, the range is L1 to L16.
3. variety_code: code indicating a unique variety in anonymized form, consisting of the letter "V" followed by a number, unitless, the range is V1 to V98.
4. proteinContent_grain_perc: wheat grain protein content, %.

Missing data codes: NA, not available

Specialized formats or other abbreviations used: n/a


DATA-SPECIFIC INFORMATION FOR: "weatherVariables_v1.0.0.csv"

Number of variables: 44

Number of cases/rows: 523

Variable List:

1. year: year in which the wheat trial was harvested, unitless.				
2. location_code: code indicating a unique location in anonymized form, consisting of the letter "L" followed by a number, unitless, the range is L1 to L16.
Variables 3 to 44 are described in "weatherVariables_units_v1.0.0.csv".

Missing data codes: NA, not available

Specialized formats or other abbreviations used: n/a 


DATA-SPECIFIC INFORMATION FOR: "weatherVariables_units_v1.0.0.csv"

Number of variables: 7

Number of cases/rows: 13

Variable List:

1. variables: names of weather-related variables included in the file "weatherVariables_v1.0.0.csv", unitless.
2. explanation: description of variables, unitless.
3. source: weather variable data were obtained from MeteoSwiss Spatial Climate Analysis products (1 km grid, https://www.meteoswiss.admin.ch/climate/the-climate-of-switzerland/spatial-climate-analyses.html) 
		   or from the nearest automatic meteorological station for each wheat trial location and year (MeteoSwiss, https://www.meteoswiss.admin.ch/weather/measurement-systems/land-based-stations/automatic-measurement-network.html),
		   unitless, raster data or weather station data.
4. units: the units in which the respective variables are expressed, unitless.
5. data_included_as: description of how weather variables are included in the dataset: as a mean, sum or number over a defined period of time, unitless.
6. period: indicators for the period of time over which weather variables are averaged, summed or a number is calculated, unitless.
7. months: months of the year that are included in a period, unitless.

Missing data codes: NA, not available

Specialized formats or other abbreviations used: n/a


DATA-SPECIFIC INFORMATION FOR: "SNP_v1.0.0.csv"

Number of variables: 12107

Number of cases/rows: 98

Variable List:

1. variety_code: code indicating a unique variety in anonymized form, consisting of the letter "V" followed by a number, unitless, the range is V1 to V98.
Variables 2 to 12107 are SNP marker names.

Missing data codes: NA, not available

Specialized formats or other abbreviations used: SNPs are encoded in the IUPAC notation (Cornish-Bowden, 1985). 

Cornish-Bowden A., 1985. Nomenclature for incompletely specified bases in nucleic acid sequences: recommendations 1984. 
Nucleic Acids Research, 13(9): 3021–3030. doi.org/10.1093/nar/13.9.3021