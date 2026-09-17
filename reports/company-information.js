/**
 * Maps Farelanes logged-in user company information (COMPANY ID / user record)
 * onto the fields used by branded reports.
 *
 * Source fields match UserService.me() / putUserMCALEI():
 * legalCompanyName, companyAddress, companyAddressLineTwo, companyCity,
 * companyState, companyZip, companyPhone, companyEmail, motorCarrierNumber,
 * dotNumber, and related identifiers.
 */

export function companyInformationFromUser(user) {
  const record = user && typeof user === "object" ? user : {};

  const legalCompanyName = firstNonEmpty(
    record.legalCompanyName,
    record.companyName,
    record.legal_business_name
  );

  return {
    legalCompanyName,
    companyAddress: firstNonEmpty(record.companyAddress, record.addressLineOne),
    companyAddressLineTwo: firstNonEmpty(
      record.companyAddressLineTwo,
      record.addressLineTwo
    ),
    companyCity: firstNonEmpty(record.companyCity, record.city),
    companyState: firstNonEmpty(record.companyState, record.state),
    companyZip: firstNonEmpty(record.companyZip, record.zip, record.zipCode),
    companyCountry: firstNonEmpty(record.companyCountry, record.country, "USA"),
    companyPhone: firstNonEmpty(record.companyPhone, record.mobileNumber),
    companyEmail: firstNonEmpty(record.companyEmail, record.email),
    motorCarrierNumber: firstNonEmpty(record.motorCarrierNumber),
    dotNumber: firstNonEmpty(record.dotNumber),
    ibrnNumber: firstNonEmpty(record.ibrnNumber, record.ibrn),
    lei: firstNonEmpty(record.lei),
    dnbNumber: firstNonEmpty(record.dnbNumber),
    companyNli: firstNonEmpty(record.companyNli, record.nlt),
    firstName: firstNonEmpty(record.firstName, record.given_name),
    lastName: firstNonEmpty(record.lastName, record.family_name),
  };
}

export function companyDisplayName(info, fallback) {
  const company = info && info.legalCompanyName ? info.legalCompanyName.trim() : "";
  if (company) {
    return company;
  }

  const person = [info && info.firstName, info && info.lastName]
    .filter(Boolean)
    .join(" ")
    .trim();
  if (person) {
    return person;
  }

  return fallback || "Farelanes Subscriber";
}

export function formatCompanyAddress(info) {
  if (!info) {
    return "";
  }

  const street = [info.companyAddress, info.companyAddressLineTwo]
    .filter(Boolean)
    .join(", ");
  const cityLine = [info.companyCity, info.companyState]
    .filter(Boolean)
    .join(", ");
  const cityZip = [cityLine, info.companyZip].filter(Boolean).join(" ");
  const country = (info.companyCountry || "").toUpperCase();
  const showCountry =
    country && country !== "USA" && country !== "US" && country !== "UNITED STATES";
  return [street, cityZip, showCountry ? info.companyCountry : ""]
    .filter(Boolean)
    .join(" · ");
}

export function formatCompanyLocation(info) {
  if (!info) {
    return "";
  }
  const cityLine = [info.companyCity, info.companyState].filter(Boolean).join(", ");
  return [cityLine, info.companyZip].filter(Boolean).join(" ");
}

export function formatCompanyMeta(info) {
  if (!info) {
    return [];
  }

  const items = [];
  if (info.motorCarrierNumber) {
    items.push({ label: "MC", value: info.motorCarrierNumber });
  }
  if (info.dotNumber) {
    items.push({ label: "USDOT", value: info.dotNumber });
  }
  return items;
}

function firstNonEmpty() {
  for (let i = 0; i < arguments.length; i += 1) {
    const value = arguments[i];
    if (value !== undefined && value !== null) {
      const text = String(value).trim();
      if (text) {
        return text;
      }
    }
  }
  return "";
}

export default {
  companyInformationFromUser,
  companyDisplayName,
  formatCompanyAddress,
  formatCompanyLocation,
  formatCompanyMeta,
};
