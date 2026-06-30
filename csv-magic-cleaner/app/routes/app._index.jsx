import { useState, useCallback, useEffect, useRef } from "react";
import { useSubmit, useLoaderData, useActionData } from "react-router";
import { Page, Layout, Card, DropZone, Button, Text, BlockStack, Banner, ProgressBar, Badge, Select, TextField, Checkbox } from "@shopify/polaris";
import { TitleBar } from "@shopify/app-bridge-react";
import { authenticate, MONTHLY_PLAN } from "../shopify.server";

// Р“Р»РѕР±Р°Р»СЊРЅР°СЏ СЃСЃС‹Р»РєР° РЅР° С‚РІРѕР№ Р±СЌРєРµРЅРґ РЅР° Render
const backendUrl = "https://magic-ai-cleaner-app.onrender.com";

// Returns a fresh Shopify session token (App Bridge) for authenticating
// requests to our backend. Call it right before each fetch — tokens are
// short-lived (~1 min) and App Bridge issues a fresh one each time.
async function authHeaders() {
  // eslint-disable-next-line no-undef
  const token = await shopify.idToken();
  return { Authorization: `Bearer ${token}` };
}

// Р­РљРЁР•Рќ: Р—Р°РїСѓСЃРєР°РµС‚ РїСЂРѕС†РµСЃСЃ РѕРїР»Р°С‚С‹
export const action = async ({ request }) => {
  const { admin, billing, session } = await authenticate.admin(request);
  const { shop } = session;

  const url = new URL(request.url);
  const formData = await request.formData();

  const fileId = formData.get("fileId");
  const forceImport = formData.get("forceImport") === "true";
  const forceProductsJson = formData.get("forceProducts");
  const downgrade = formData.get("downgrade") === "true";

  if (downgrade) {
    // 1.2.3: merchants must be able to move from Pro back to Free without
    // contacting support or reinstalling the app, and the cancellation must be
    // confirmed in the merchant's app charge history (Settings > Billing).
    const { appSubscriptions } = await billing.check({ plans: [MONTHLY_PLAN] });
    const activeSub = appSubscriptions?.[0];

    if (!activeSub) {
      // Already on Free — nothing to cancel.
      return { downgraded: true };
    }

    try {
      const cancelled = await billing.cancel({ subscriptionId: activeSub.id, prorate: true });
      if (cancelled?.status !== "CANCELLED") {
        return { downgradeError: `Subscription status after cancel: ${cancelled?.status || "unknown"}` };
      }
      return { downgraded: true };
    } catch (err) {
      return { downgradeError: err instanceof Error ? err.message : "Failed to cancel subscription" };
    }
  }

  if (fileId || forceProductsJson) {
    let products;

    if (forceProductsJson) {
      // Повторный импорт дублей по кнопке "Add anyway"
      products = JSON.parse(forceProductsJson);
    } else {
      // Server-to-server call from the app server to our backend — authenticated
      // with a shared secret (the browser session token is not available here).
      const backendRes = await fetch(`https://magic-ai-cleaner-app.onrender.com/products/${fileId}`, {
        // eslint-disable-next-line no-undef
        headers: { "X-Backend-Secret": process.env.BACKEND_SHARED_SECRET || "" },
      });
      const data = await backendRes.json();
      if (!data.products || !Array.isArray(data.products)) {
        return { error: data.error || "No products found", imported: 0, total: 0, errors: [], duplicates: [] };
      }
      products = data.products;
    }

    let created = 0;
    let errors = [];
    let duplicates = [];

    const importOne = async (product) => {
      for (let attempt = 0; attempt < 3; attempt++) {
        try {
          const handle = forceImport
            ? product.title.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "") + "-" + Date.now()
            : undefined;
          const input = {
            title: product.title,
            descriptionHtml: product.descriptionHtml,
            vendor: product.vendor,
            productType: product.productType,
            tags: product.tags,
            ...(handle ? { handle } : {}),
          };
          const response = await admin.graphql(
            `#graphql
            mutation productCreate($input: ProductInput!) {
              productCreate(input: $input) {
                product { id title }
                userErrors { field message }
              }
            }`,
            { variables: { input } }
          );
          const json = await response.json();
          if (json.errors?.[0]?.extensions?.code === "THROTTLED") {
            await new Promise(r => setTimeout(r, 1000 * (attempt + 1)));
            continue;
          }
          const userErrors = json.data?.productCreate?.userErrors ?? [];
          const handleTaken = userErrors.some(e => e.message?.includes("Handle has already been taken"));
          if (handleTaken) {
            return { ok: false, duplicate: true, product };
          }
          if (userErrors.length > 0) {
            return { ok: false, errors: userErrors };
          }
          return { ok: true };
        } catch {
          if (attempt === 2) return { ok: false, errors: [{ message: "Request failed" }] };
          await new Promise(r => setTimeout(r, 500));
        }
      }
      return { ok: false, errors: [{ message: "Max retries exceeded" }] };
    };

    const results = await Promise.all(products.map(importOne));
    for (const result of results) {
      if (result.ok) created++;
      else if (result.duplicate) duplicates.push(result.product);
      else if (result.errors) errors.push(...result.errors);
    }

    return { imported: created, total: products.length, errors: errors.slice(0, 5), duplicates };
  }

  // No import payload → this is an upgrade request. Use the Shopify Billing API:
  // require the Pro plan, and on failure request it (redirects the merchant to
  // Shopify's hosted payment confirmation screen).
  const pathParts = url.pathname.split("/");
  const appHandle = pathParts[pathParts.indexOf("apps") + 1] || "csv-magic-cleaner";
  const returnUrl = `https://${shop}/admin/apps/${appHandle}/app`;

  try {
    await billing.require({
      plans: [MONTHLY_PLAN],
      onFailure: async () => {
        throw await billing.request({ plan: MONTHLY_PLAN, returnUrl });
      },
    });
    return { success: true };
  } catch (error) {
    if (error instanceof Response && error.status === 401) {
      const redirectUrl = error.headers.get("X-Shopify-API-Request-Failure-Reauthorize-Url");
      if (redirectUrl) {
        return { redirectUrl };
      }
    }
    throw error;
  }
};

// Р›РћРђР”Р•Р : РџСЂРѕРІРµСЂРєР° СЃС‚Р°С‚СѓСЃР° РїРѕРґРїРёСЃРєРё
export const loader = async ({ request }) => {
  const { session, billing } = await authenticate.admin(request);

  const checkResult = await billing.check({ plans: [MONTHLY_PLAN] });
  const isPro = checkResult === true || checkResult?.hasActivePayment === true;

  return {
    shop: session.shop,
    isPro,
    shopDomain: session.shop,
  };
};

export default function Index() {
  const { isPro } = useLoaderData();
  const submit = useSubmit();
  const actionData = useActionData();

  // Trigger the Shopify Billing API upgrade flow: POST to the action with no file
  // payload → billing.require/request → Shopify's hosted payment screen.
  const goToPricing = useCallback(() => {
    submit({}, { method: "post" });
  }, [submit]);

  // 1.2.3: let merchants downgrade from Pro back to Free in-app, no support
  // ticket or reinstall required. Cancels the active subscription directly.
  const [isDowngrading, setIsDowngrading] = useState(false);
  const goToDowngrade = useCallback(() => {
    setIsDowngrading(true);
    const fd = new FormData();
    fd.append("downgrade", "true");
    submit(fd, { method: "post" });
  }, [submit]);

  useEffect(() => {
    if (actionData?.downgraded || actionData?.downgradeError) {
      setIsDowngrading(false);
    }
  }, [actionData]);

  const [file, setFile] = useState(null);
  const [tone, setTone] = useState("Neutral & Professional");
  const [supplierName, setSupplierName] = useState("");
  const [genSeo, setGenSeo] = useState(false);
  const [genAlt, setGenAlt] = useState(false);
  const [consent, setConsent] = useState(false);
  const [isProcessing, setIsProcessing] = useState(false);
  const [message, setMessage] = useState("");
  const [progress, setProgress] = useState(0);
  const [fileId, setFileId] = useState(null);
  const [statusText, setStatusText] = useState("");
  const [isCompleted, setIsCompleted] = useState(false);
  const [previewRows, setPreviewRows] = useState([]);
  const [totalProcessed, setTotalProcessed] = useState(0);
  const [isImporting, setIsImporting] = useState(false);
  const importResultRef = useRef(null);

  useEffect(() => {
    if (actionData?.redirectUrl) {
      window.open(actionData.redirectUrl, "_top");
    }
  }, [actionData]);

  // Сбросить isImporting и автоскролл к результату когда пришёл ответ
  useEffect(() => {
    if (actionData?.imported !== undefined || actionData?.error !== undefined) {
      setIsImporting(false);
      setTimeout(() => {
        importResultRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
      }, 100);
    }
  }, [actionData]);

  const handleDropZoneDrop = useCallback((_dropFiles, acceptedFiles) => {
    setFile(acceptedFiles[0]);
    setMessage("");
    setProgress(0);
    setFileId(null);
    setIsCompleted(false);
    setStatusText("");
    setTotalProcessed(0);
  }, []);

  const handleToneChange = useCallback((value) => setTone(value), []);

  const toneOptions = [
    {label: 'Neutral & Professional', value: 'Neutral & Professional'},
    {label: 'Enthusiastic & Sales-driven', value: 'Enthusiastic & Sales-driven'},
    {label: 'Luxury & Elegant', value: 'Luxury & Elegant'},
    {label: 'Fun & Playful', value: 'Fun & Playful'},
    {label: 'Minimalist & Direct', value: 'Minimalist & Direct'}
  ];

  const handleProcess = async () => {
    if (!file) return;
    setIsProcessing(true);
    setMessage("");
    setProgress(0);
    setIsCompleted(false);
    setStatusText("Uploading file...");
    setTotalProcessed(0);

    const formData = new FormData();
    formData.append("file", file);
    formData.append("is_pro", isPro ? "true" : "false");
    formData.append("tone", tone);
    if (supplierName.trim()) {
      formData.append("supplier_name", supplierName.trim());
    }
    if (genSeo) formData.append("seo", "true");
    if (genAlt) formData.append("alt", "true");

    try {
      // shop is derived from the verified session token on the backend
      const response = await fetch(`${backendUrl}/upload`, {
        method: "POST",
        headers: await authHeaders(),
        body: formData,
      });

      const data = await response.json();
      if (!response.ok) throw new Error(data.error || "Server error");
      setFileId(data.file_id); 
    } catch (error) {
      setMessage(`Error: ${error.message}`);
      setIsProcessing(false);
    }
  };

useEffect(() => {
    let interval;
    if (isProcessing && fileId && !isCompleted) {
      interval = setInterval(async () => {
        try {
          const response = await fetch(`${backendUrl}/status/${fileId}`, { headers: await authHeaders() });
          const data = await response.json();
          if (data.status === "completed") {
            setIsCompleted(true);
            setIsProcessing(false);
            setProgress(100);
            if (data.total > 0) setTotalProcessed(data.total);
            setMessage("Magic completed!");
            clearInterval(interval);
            fetch(`${backendUrl}/preview/${fileId}?limit=5`, { headers: await authHeaders() })
              .then(r => r.json())
              .then(d => {
                console.log("PREVIEW response:", d);
                if (d.rows && Array.isArray(d.rows)) {
                  setPreviewRows(d.rows);
                }
              })
              .catch(e => console.error("Preview fetch error:", e));
          } else if (data.status === "error") {
            setIsProcessing(false);
            setMessage(`Error: ${data.error || "Processing error"}`);
            clearInterval(interval);
          } else if (data.total > 0) {
            const currentProgress = Math.round((data.current / data.total) * 100);
            setProgress(currentProgress);
            setTotalProcessed(data.total);
            setStatusText(`Processing: ${data.current} of ${data.total}...`);
          }
        } catch (error) {
          console.error("Status error:", error);
        }
      }, 1000); 
    }
    return () => clearInterval(interval);
  }, [isProcessing, fileId, isCompleted]);

const handleImportShopify = () => {
    setIsImporting(true);
    const formData = new FormData();
    formData.append("fileId", fileId);
    submit(formData, { method: "post" });
  };

  return (
    <Page>
      <TitleBar title="CSV Magic Cleaner" />
      <Layout>
        <Layout.Section>
          <Card>
            <BlockStack gap="400">
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <Text as="h2" variant="headingMd">AI CSV Cleaner</Text>
                {isPro && <Badge tone="success">Pro Plan Active</Badge>}
              </div>

              {/* Pricing info — always visible so reviewers and merchants understand the billing flow */}
              {!isPro && (
                <Banner tone="info">
                  <BlockStack gap="100">
                    <Text as="p" variant="bodyMd" fontWeight="bold">Free plan: up to 150 products / month</Text>
                    <Text as="p" variant="bodyMd">Upload your CSV and let AI rewrite your product descriptions. Once you reach the 150-product limit, upgrade to the Pro plan ($19.99/mo). Payment is handled entirely through Shopify's secure checkout — no external accounts or cards.</Text>
                    <Text as="p" variant="bodyMd">Pro plan unlocks: unlimited products, AI-generated SEO titles, meta descriptions, and image alt text.</Text>
                    <div style={{ marginTop: "8px" }}>
                      <Button onClick={goToPricing} variant="plain">
                        Upgrade to Pro — $19.99/mo →
                      </Button>
                    </div>
                  </BlockStack>
                </Banner>
              )}

              {/* 1.2.3: merchants must be able to downgrade without contacting support */}
              {isPro && (
                <Banner tone="info">
                  <BlockStack gap="100">
                    <Text as="p" variant="bodyMd">You're on the Pro plan ($19.99/mo, unlimited products). You can cancel anytime — your plan will move back to Free immediately and the change is reflected in your store's billing history.</Text>
                    <div style={{ marginTop: "8px" }}>
                      <Button onClick={goToDowngrade} variant="plain" tone="critical" loading={isDowngrading} disabled={isDowngrading}>
                        Downgrade to Free
                      </Button>
                    </div>
                  </BlockStack>
                </Banner>
              )}

              {actionData?.downgraded && !isPro && (
                <Banner tone="success">You're now on the Free plan (up to 150 products/month).</Banner>
              )}
              {actionData?.downgradeError && (
                <Banner tone="critical">Could not cancel your subscription: {actionData.downgradeError}. Please try again.</Banner>
              )}

              <DropZone onDrop={handleDropZoneDrop} accept=".csv">
                {file ? (
                  <div style={{ padding: "20px", textAlign: "center" }}>
                    <Text variant="bodyMd" fontWeight="bold">{file.name}</Text>
                  </div>
                ) : <DropZone.FileUpload />}
              </DropZone>

              <TextField
                label="Supplier name (optional — save mapping for future uploads)"
                value={supplierName}
                onChange={setSupplierName}
                autoComplete="off"
                placeholder="e.g. MySupplier_PetProducts"
                disabled={isProcessing || isCompleted}
              />

              <Select
                label="Tone of Voice"
                options={toneOptions}
                onChange={handleToneChange}
                value={tone}
                disabled={isProcessing || isCompleted}
              />

              {isPro && (
                <BlockStack gap="200">
                  <Checkbox label="Generate SEO Title & Meta Description" checked={genSeo} onChange={setGenSeo} disabled={isProcessing || isCompleted} />
                  <Checkbox label="Generate Image Alt Text" checked={genAlt} onChange={setGenAlt} disabled={isProcessing || isCompleted} />
                </BlockStack>
              )}

              {!isCompleted && (
                <BlockStack gap="200">
                  <Checkbox
                    label="I confirm that I own these products or have the rights to import, list, and sell them in my store."
                    checked={consent}
                    onChange={setConsent}
                    disabled={isProcessing}
                  />
                  <Button variant="primary" onClick={handleProcess} loading={isProcessing} disabled={!file || isProcessing || !consent}>
                    Start AI Magic
                  </Button>
                </BlockStack>
              )}

              {isProcessing && (
                <BlockStack gap="200">
                  <Text as="p" variant="bodyMd" tone="subdued">{statusText}</Text>
                  <ProgressBar progress={progress} tone="primary" />
                </BlockStack>
              )}

              {message && (
                <Banner tone={message.includes("Error") ? "critical" : "success"}>
                  <BlockStack gap="200">
                    <p>{message}</p>
                    {message.includes("Limit exceeded") && !isPro && (
                      <div style={{ marginTop: '10px' }}>
                        <Button onClick={goToPricing} variant="primary">
                          Upgrade to Pro ($19.99/mo)
                        </Button>
                      </div>
                    )}
                  </BlockStack>
                </Banner>
              )}

              {isCompleted && (
                <BlockStack gap="300">
                  {totalProcessed > 0 && (
                    <Banner tone="success">
                      ✓ {totalProcessed} products processed and ready to import
                    </Banner>
                  )}
                  {previewRows.length > 0 && (
                    <Card>
                      <Text as="h3" variant="headingSm">Preview (first {previewRows.length} items)</Text>
                      <div style={{ overflowX: "auto", marginTop: "8px" }}>
                        <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "12px" }}>
                          <thead>
                            <tr style={{ backgroundColor: "#f1f1f1" }}>
                              <th style={{ padding: "6px", textAlign: "left", border: "1px solid #ddd" }}>Title</th>
                              <th style={{ padding: "6px", textAlign: "left", border: "1px solid #ddd" }}>AI Description</th>
                              <th style={{ padding: "6px", textAlign: "left", border: "1px solid #ddd" }}>Price</th>
                              <th style={{ padding: "6px", textAlign: "left", border: "1px solid #ddd" }}>Type</th>
                            </tr>
                          </thead>
                          <tbody>
                            {previewRows.map((row, i) => (
                              <tr key={i}>
                                <td style={{ padding: "6px", border: "1px solid #ddd", verticalAlign: "top" }}>{row.title}</td>
                                <td style={{ padding: "6px", border: "1px solid #ddd", verticalAlign: "top", maxWidth: "300px" }}>
                                  <div dangerouslySetInnerHTML={{ __html: row.body_html?.substring(0, 200) + (row.body_html?.length > 200 ? "..." : "") }} />
                                </td>
                                <td style={{ padding: "6px", border: "1px solid #ddd", whiteSpace: "nowrap" }}>{row.price}</td>
                                <td style={{ padding: "6px", border: "1px solid #ddd", whiteSpace: "nowrap" }}>{row.product_type}</td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    </Card>
                  )}
                  <Button variant="primary" size="large" onClick={handleImportShopify} loading={isImporting} disabled={isImporting}>
                    Import to Shopify Store
                  </Button>

                  {isImporting && (
                    <BlockStack gap="200">
                      <Text as="p" variant="bodyMd" tone="subdued">Importing products to Shopify...</Text>
                      <ProgressBar progress={0} tone="primary" />
                    </BlockStack>
                  )}

                  <div ref={importResultRef} />
                  {actionData?.imported !== undefined && (
                    <Banner tone={actionData.error ? "critical" : (actionData.errors?.length > 0 || actionData.duplicates?.length > 0) ? "warning" : "success"}>
                      {actionData.error
                        ? actionData.error
                        : `Imported ${actionData.imported}/${actionData.total} products`}
                      {actionData.duplicates?.length > 0 && (
                        <div style={{marginTop: "8px"}}>
                          <strong>{actionData.duplicates.length} already exist in your catalog:</strong>
                          <ul style={{marginTop: "4px", paddingLeft: "16px"}}>
                            {actionData.duplicates.map((p, i) => <li key={i}>{p.title}</li>)}
                          </ul>
                          <div style={{marginTop: "8px"}}>
                            <Button
                              size="slim"
                              onClick={() => {
                                const fd = new FormData();
                                fd.append("forceProducts", JSON.stringify(actionData.duplicates));
                                fd.append("forceImport", "true");
                                submit(fd, { method: "post" });
                              }}
                            >
                              Add anyway
                            </Button>
                          </div>
                        </div>
                      )}
                      {actionData.errors?.length > 0 && !actionData.error && (
                        <div style={{marginTop: "8px"}}>
                          <strong>{actionData.errors.length} failed:</strong>
                          <ul style={{marginTop: "4px", paddingLeft: "16px"}}>
                            {actionData.errors.map((e, i) => (
                              <li key={i}>{e.field ? `${e.field}: ` : ""}{e.message}</li>
                            ))}
                          </ul>
                        </div>
                      )}
                    </Banner>
                  )}
                </BlockStack>
              )}
            </BlockStack>
          </Card>
        </Layout.Section>
      </Layout>
    </Page>
  );
}
