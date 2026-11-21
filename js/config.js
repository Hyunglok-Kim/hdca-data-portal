/* Deployment settings. The portal itself is a static site; everything that differs between
   the lab-internal copy and the public one lives here (or in the URL, see below).

   dataBase      where catalog.json and the field archives live. A page may override it with
                 ?data=/some/path/ — same-origin paths only, so a link cannot point the map at
                 someone else's files.
   seriesBase    where the per-cell series store lives when it is not next to the fields. The public
                 copy keeps it in a second GitHub Pages repository on the same origin (one site holds
                 at most 1 GB). Empty = same place as dataBase; a ?data= override always uses that place.
   zenodo        the public release: the record's DOI and page, and its files (one NetCDF per year) with the
                 sizes and MD5 sums Zenodo reports. The Download tab lists them with direct links and the code
                 examples read them. The lab storage keeps the daily files and the merged file (nasPath, below).
   ncBase        an alternative public address of the lab's daily/merged files (none at present; the Zenodo
                 release is per year). Empty = the Download tab shows the lab storage path to members only.
   contactEmail  where questions about the data go. */
window.PORTAL_CONFIG = {
  dataBase: "./data/",
  seriesBase: "https://hyunglok-kim.github.io/hdca-data-portal-series/",
  ncBase: "",
  zenodo: {
    doi: "10.5281/zenodo.24359287",
    url: "https://doi.org/10.5281/zenodo.24359287",
    record: "https://zenodo.org/records/24359287",
    license: "CC BY 4.0",
    published: "2026-11-20",
    files: [
      { name: "HDCA_2015.nc", year: 2015, bytes: 322383238, md5: "c68e4bb54e6de13f47723140e9373676" },
      { name: "HDCA_2016.nc", year: 2016, bytes: 375795788, md5: "4a2bbecf78eb3ddcd1a8bfc2c7634f82" },
      { name: "HDCA_2017.nc", year: 2017, bytes: 381599134, md5: "13637069dbf12bc31c665066d909a4bc" },
      { name: "HDCA_2018.nc", year: 2018, bytes: 375562677, md5: "a7078431230ee9a97c87629e9bb08226" },
      { name: "HDCA_2019.nc", year: 2019, bytes: 340968114, md5: "f754fc75defabd884a7f98f727fdc351" },
      { name: "HDCA_2020.nc", year: 2020, bytes: 380262801, md5: "61530c8df3fc9477830dd0e89cca5e9d" },
      { name: "HDCA_2021.nc", year: 2021, bytes: 382713059, md5: "57452afcfd8ed488bd6eaeb7cac53062" },
      { name: "HDCA_2022.nc", year: 2022, bytes: 324793384, md5: "4fa6afeb96fc9d7102d6c653436ee642" },
      { name: "HDCA_2023.nc", year: 2023, bytes: 382073283, md5: "a30d4be63eaeed210be014320f25bf8f" },
      { name: "HDCA_2024.nc", year: 2024, bytes: 379673917, md5: "47fbea2b5eba44d1a94ad92636bc1dab" },
      { name: "HDCA_2025.nc", year: 2025, bytes: 376747161, md5: "4f39956f895d8a5881bd31df49ebd694" },
    ],
  },
  contactEmail: "hyunglokkim@gist.ac.kr",
  dataContact: "Jaese Lee (first author)",
};
