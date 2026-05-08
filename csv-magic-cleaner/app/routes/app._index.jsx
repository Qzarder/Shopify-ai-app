import { useState, useCallback, useEffect } from "react";
import { useSubmit, useLoaderData, useActionData } from "react-router";
import { Page, Layout, Card, DropZone, Button, Text, BlockStack, Banner, ProgressBar, Badge, Select, TextField } from "@shopify/polaris";
import { TitleBar } from "@shopify/app-bridge-react";
import { authenticate, MONTHLY_PLAN } from "../shopify.server";

// Р“Р»РѕР±Р°Р»СЊРЅР°СЏ СЃСЃС‹Р»РєР° РЅР° С‚РІРѕР№ Р±СЌРєРµРЅРґ РЅР° Render
const backendUrl = "https://magic-ai-cleaner-app.onrender.com";

// Р­РљРЁР•Рќ: Р—Р°РїСѓСЃРєР°РµС‚ РїСЂРѕС†РµСЃСЃ РѕРїР»Р°С‚С‹
export const action = async ({ request }) => {
  const { billing, session, admin } = await authenticate.admin(request);
  const { shop } = session;

  const url = new URL(request.url);
  const formData = await request.formData();

  const fileId = formData.get("fileId");
  if (fileId) {
const backendRes = await fetch(`https://magic-ai-cleaner-app.onrender.com/products/${fileId}`);
      const data = await backendRes.json();
      if (!data.products || !Array.isArray(data.products)) {
        return { error: data.error || "No products found", imported: 0, total: 0, errors: [] };
      }
      const { products } = data;

let created = 0;
      let errors = [];
      for (const product of products) {
        const response = await admin.graphql(
          `#graphql
          mutation productCreate($input: ProductCreateInput!) {
            productCreate(product: $input) {
              product { id title }
              userErrors { field message }
            }
          }`,
          { variables: {
            input: {
              title: product.title,
              descriptionHtml: product.descriptionHtml,
              vendor: product.vendor,
              productType: product.productType,
              tags: product.tags,
            }
          }}
        );
      const json = await response.json();
      if (json.data.productCreate.userErrors.length > 0) {
        errors.push(...json.data.productCreate.userErrors);
      } else {
        created++;
      }
    }
    return { imported: created, total: products.length, errors: errors.slice(0, 5) };
  }

  const pathParts = url.pathname.split('/');
  const appHandle = pathParts[pathParts.indexOf('apps') + 1] || "csv-magic-cleaner";
  const returnUrl = `https://${shop}/admin/apps/${appHandle}/app`;

  try {
    await billing.require({
      plans: [MONTHLY_PLAN],
      isTest: true,
      onFailure: async () => {
        throw await billing.request({
          plan: MONTHLY_PLAN,
          isTest: true,
          returnUrl: returnUrl,
        });
      }
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
  
  const checkResult = await billing.check({
    plans: [MONTHLY_PLAN],
    isTest: true,
  });

  console.log("[BILLING DEBUG] checkResult:", JSON.stringify(checkResult));

  const isPro = checkResult === true || checkResult?.hasActivePayment === true;

  return { 
    shop: session.shop, 
    isPro: isPro,
    shopDomain: session.shop
  };
};

export default function Index() {
  const { shop, isPro, shopDomain } = useLoaderData();
  const submit = useSubmit();
  const actionData = useActionData();
  
  const [file, setFile] = useState(null);
  const [tone, setTone] = useState("Neutral & Professional");
  const [supplierName, setSupplierName] = useState("");
  const [isProcessing, setIsProcessing] = useState(false);
  const [message, setMessage] = useState("");
  const [progress, setProgress] = useState(0);
  const [fileId, setFileId] = useState(null);
  const [statusText, setStatusText] = useState("");
  const [isCompleted, setIsCompleted] = useState(false);

  useEffect(() => {
    if (actionData?.redirectUrl) {
      window.open(actionData.redirectUrl, "_top");
    }
  }, [actionData]);

  const handleDropZoneDrop = useCallback((_dropFiles, acceptedFiles) => {
    setFile(acceptedFiles[0]);
    setMessage("");
    setProgress(0);
    setFileId(null);
    setIsCompleted(false);
    setStatusText("");
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

    const formData = new FormData();
    formData.append("file", file);
formData.append("shop", shopDomain || shop); 
    formData.append("is_pro", isPro ? "true" : "false"); 
    formData.append("tone", tone);
    if (supplierName.trim()) {
      formData.append("supplier_name", supplierName.trim());
    }

    try {
      // Используем глобальный backendUrl
      const response = await fetch(`${backendUrl}/upload`, {
        method: "POST",
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
          // Р—РђРњР•РќР•РќРћ: localhost -> backendUrl
          const response = await fetch(`${backendUrl}/status/${fileId}`);
          const data = await response.json();
          if (data.status === "completed") {
            setIsCompleted(true);
            setIsProcessing(false);
            setProgress(100);
            setMessage("Magic completed!");
            clearInterval(interval);
          } else if (data.status === "error") {
            setIsProcessing(false);
            setMessage(`Error: ${data.error || "Processing error"}`);
            clearInterval(interval);
          } else if (data.total > 0) {
            const currentProgress = Math.round((data.current / data.total) * 100);
            setProgress(currentProgress);
            setStatusText(`Processing: ${data.current} of ${data.total}...`);
          }
        } catch (error) {
          console.error("Status error:", error);
        }
      }, 1000); 
    }
    return () => clearInterval(interval);
  }, [isProcessing, fileId, isCompleted]);

const handleImportShopify = async () => {
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
                placeholder="e.g. AliExpress_PetCo"
                disabled={isProcessing || isCompleted}
              />

              <Select
                label="Tone of Voice"
                options={toneOptions}
                onChange={handleToneChange}
                value={tone}
                disabled={isProcessing || isCompleted}
              />

              {!isCompleted && (
                <Button variant="primary" onClick={handleProcess} loading={isProcessing} disabled={!file || isProcessing}>
                  Start AI Magic
                </Button>
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
                        <Button onClick={() => submit({}, { method: "post" })} variant="primary">
                          Upgrade to Pro ($19.99/mo)
                        </Button>
                      </div>
                    )}
                  </BlockStack>
                </Banner>
              )}

              {isCompleted && (
                <BlockStack gap="300">
                  <Button variant="primary" size="large" onClick={handleImportShopify} loading={actionData && !actionData.imported}>
                    Import to Shopify Store
                  </Button>
                  {actionData?.imported !== undefined && (
                    <Banner tone={actionData.errors?.length > 0 ? "warning" : "success"}>
                      Imported {actionData.imported}/{actionData.total} products
                      {actionData.errors?.length > 0 && `. Skipped: ${actionData.errors.length}`}
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
