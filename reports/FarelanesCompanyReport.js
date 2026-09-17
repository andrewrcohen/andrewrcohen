import { useEffect, useMemo, useState } from "react";
import { useAuth0 } from "@auth0/auth0-react";
import html2pdf from "html2pdf.js";
import UserService from "../services/UserService";
import {
  companyDisplayName,
  companyInformationFromUser,
} from "./company-information";

const DEFAULT_TITLE = "Farelanes Market Intelligence Report";

export function FarelanesCompanyReport(props) {
  const title = props.title || DEFAULT_TITLE;
  const { getAccessTokenSilently, user } = useAuth0();
  const [companyInfo, setCompanyInfo] = useState(
    companyInformationFromUser(props.companyInformation || {})
  );
  const [loadState, setLoadState] = useState(props.companyInformation ? "ready" : "loading");

  useEffect(() => {
    if (props.companyInformation) {
      setCompanyInfo(companyInformationFromUser(props.companyInformation));
      setLoadState("ready");
      return undefined;
    }

    let cancelled = false;

    const loadLoggedInCompany = async () => {
      try {
        const token = await getAccessTokenSilently();
        const response = await UserService.me(token, user);
        if (cancelled) {
          return;
        }
        setCompanyInfo(companyInformationFromUser(response.data || {}));
        setLoadState("ready");
      } catch (error) {
        if (!cancelled) {
          setLoadState("error");
          console.error("Unable to load Farelanes company information", error);
        }
      }
    };

    loadLoggedInCompany();
    return () => {
      cancelled = true;
    };
  }, [getAccessTokenSilently, props.companyInformation, user]);

  const reportUrl = useMemo(
    () => buildReportUrl(title, companyInfo),
    [companyInfo, title]
  );

  const displayName = companyDisplayName(companyInfo);

  const downloadPdf = async () => {
    const frame = document.getElementById("farelanes-company-report-frame");
    const element = frame && frame.contentDocument
      ? frame.contentDocument.getElementById("farelanes-report")
      : null;
    if (!element) {
      return;
    }

    const filename = `Farelanes_Report_${displayName.replace(/\s+/g, "_")}.pdf`;
    await html2pdf()
      .set({
        margin: 0,
        filename,
        image: { type: "jpeg", quality: 0.98 },
        html2canvas: { scale: 2, useCORS: true },
        jsPDF: { unit: "in", format: "letter", orientation: "landscape" },
        pagebreak: { mode: ["css", "legacy"] },
      })
      .from(element)
      .save();
  };

  switch (loadState) {
    case "loading":
      return <div className="farelanes-report-status">Loading company information…</div>;
    case "error":
      return (
        <div className="farelanes-report-status">
          Company information could not be loaded for the logged-in user.
        </div>
      );
    case "ready":
      return (
        <div>
          <div className="toolbar">
            <button type="button" onClick={downloadPdf}>
              Download PDF
            </button>
          </div>
          <iframe
            id="farelanes-company-report-frame"
            className="farelanes-report-frame"
            title={title}
            src={reportUrl}
            style={{ width: "11in", height: "17.4in", border: 0 }}
          />
        </div>
      );
    default: {
      const exhaustiveCheck = loadState;
      throw new Error(`Unhandled report load state: ${exhaustiveCheck}`);
    }
  }
}

function buildReportUrl(title, companyInfo) {
  const params = new URLSearchParams();
  params.set("title", title);
  if (companyInfo.legalCompanyName) {
    params.set("legalCompanyName", companyInfo.legalCompanyName);
  }
  if (companyInfo.companyAddress) {
    params.set("companyAddress", companyInfo.companyAddress);
  }
  if (companyInfo.companyAddressLineTwo) {
    params.set("companyAddressLineTwo", companyInfo.companyAddressLineTwo);
  }
  if (companyInfo.companyCity) {
    params.set("companyCity", companyInfo.companyCity);
  }
  if (companyInfo.companyState) {
    params.set("companyState", companyInfo.companyState);
  }
  if (companyInfo.companyZip) {
    params.set("companyZip", companyInfo.companyZip);
  }
  if (companyInfo.companyPhone) {
    params.set("companyPhone", companyInfo.companyPhone);
  }
  if (companyInfo.motorCarrierNumber) {
    params.set("mc", companyInfo.motorCarrierNumber);
  }
  if (companyInfo.dotNumber) {
    params.set("dot", companyInfo.dotNumber);
  }
  return `reports/farelanes-company-report.html?${params.toString()}`;
}

export default FarelanesCompanyReport;
