# IIMS Accession Number Test -- Investigation Summary

## Background

The IIMS test sends a DICOM study with a blank AccessionNumber to Compass, expecting Compass to call the IIMS web service to generate one. The study arrives at the destination but AccessionNumber remains empty. No "iims" entries appear in compass-service logs.

## AE Title Roles

- **Called AE (SCP):** The server/listener receiving the request. `TEAM_INT_SCP` is for storing images; `CLINICAL_SCP` is for C-FIND queries against MIDIA.
- **Calling AE (SCU):** The client initiating the request. Determines routing rules. `TEAM_SCP` is required when connecting to `CLINICAL_SCP`.

## Combinations Tested

| AccessionNumber | Calling AE (SCU) | Called AE (SCP) | Result |
|---|---|---|---|
| Empty string | HTM-GI | CLINICAL_SCP | No IIMS call |
| Empty string | HTM-GI | TEAM_INT_SCP | No IIMS call |
| Tag removed | TEAM_SCP | TEAM_INT_SCP | No IIMS call |
| Empty string | TEAM_SCP | TEAM_INT_SCP | No IIMS call |

In all cases the study was accepted, routed, and delivered to the destination successfully.

## Conclusion

The IIMS GetAccessionNumber rule is not configured on this Compass instance. The test automation is working correctly. The Compass admin needs to enable the IIMS web service integration before this test case can be validated.
