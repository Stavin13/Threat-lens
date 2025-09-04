import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { PageHeader } from "@/components/page-header"
import { FileUploadForm } from "@/components/ingest/file-upload-form"
import { TextIngestForm } from "@/components/ingest/text-ingest-form"

export default function IngestPage() {
  return (
    <>
      <PageHeader
        title="Log Ingestion"
        description="Upload files or send text content to /ingest-log. Console: /api/ingest/text."
      />
      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle className="text-base">File Upload</CardTitle>
          </CardHeader>
          <CardContent>
            <FileUploadForm />
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Paste Text</CardTitle>
          </CardHeader>
          <CardContent>
            <TextIngestForm />
          </CardContent>
        </Card>
      </div>
    </>
  )
}
