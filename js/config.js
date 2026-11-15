/* Deployment settings. The portal itself is a static site; everything that differs between
   the lab-internal copy and the public one lives here (or in the URL, see below).

   dataBase      where catalog.json and the field archives live. A page may override it with
                 ?data=/some/path/ — same-origin paths only, so a link cannot point the map at
                 someone else's files.
   seriesBase    where the per-cell series store lives when it is not next to the fields. The public
                 copy keeps it in a second GitHub Pages repository on the same origin (one site holds
                 at most 1 GB). Empty = same place as dataBase; a ?data= override always uses that place.
   ncBase        public address of the NetCDF files. Empty until they are deposited; the Download tab
                 then shows the lab storage path (internal copy) or a contact address (public copy).
   contactEmail  where questions about the data go. */
window.PORTAL_CONFIG = {
  dataBase: "./data/",
  seriesBase: "https://hyunglok-kim.github.io/hdca-data-portal-series/",
  ncBase: "",
  contactEmail: "hyunglokkim@gist.ac.kr",
  dataContact: "Jaese Lee (first author)",
};
