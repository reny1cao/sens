'use client';

import { useCallback, useState } from 'react';
import { useDropzone } from 'react-dropzone';
import { Upload, File, X, Loader2 } from 'lucide-react';
import { cn } from '@/lib/utils';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { useDataSource } from '@/contexts/DataSourceContext';

const MAX_FILE_SIZE = 100 * 1024 * 1024; // 100MB
const ACCEPTED_FILE_TYPES = {
  'text/csv': ['.csv'],
  'application/vnd.ms-excel': ['.xls'],
  'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': ['.xlsx'],
};

interface FileUploadProps {
  onSuccess?: () => void;
}

export function FileUpload({ onSuccess }: FileUploadProps = {}) {
  const { uploadFiles, isLoading, error } = useDataSource();
  const [files, setFiles] = useState<File[]>([]);
  const [uploadError, setUploadError] = useState<string | null>(null);

  const onDrop = useCallback((acceptedFiles: File[], rejectedFiles: any[]) => {
    setUploadError(null);
    
    if (rejectedFiles.length > 0) {
      const errors = rejectedFiles.map(({ file, errors }) => {
        const errorMessages = errors.map((e: any) => {
          if (e.code === 'file-too-large') return `${file.name} is too large (max 100MB)`;
          if (e.code === 'file-invalid-type') return `${file.name} has invalid type`;
          return e.message;
        }).join(', ');
        return errorMessages;
      }).join('; ');
      
      setUploadError(errors);
      return;
    }

    setFiles(acceptedFiles);
  }, []);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: ACCEPTED_FILE_TYPES,
    maxSize: MAX_FILE_SIZE,
    multiple: true,
  });

  const handleUpload = async () => {
    if (files.length === 0) return;

    try {
      await uploadFiles(files);
      setFiles([]);
      onSuccess?.();
    } catch (err) {
      // Error is handled by context
    }
  };

  const removeFile = (index: number) => {
    setFiles(prev => prev.filter((_, i) => i !== index));
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle>Upload Data Files</CardTitle>
        <CardDescription>
          Upload CSV or Excel files to query your own data
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div
          {...getRootProps()}
          className={cn(
            "border-2 border-dashed rounded-lg p-8 text-center cursor-pointer transition-colors",
            isDragActive ? "border-primary bg-primary/5" : "border-muted-foreground/25 hover:border-primary/50",
            isLoading && "pointer-events-none opacity-50"
          )}
        >
          <input {...getInputProps()} />
          <Upload className="mx-auto h-12 w-12 text-muted-foreground mb-4" />
          {isDragActive ? (
            <p className="text-lg font-medium">Drop the files here...</p>
          ) : (
            <>
              <p className="text-lg font-medium mb-1">
                Drag & drop files here, or click to select
              </p>
              <p className="text-sm text-muted-foreground">
                Supports CSV and Excel files (max 100MB each)
              </p>
            </>
          )}
        </div>

        {(uploadError || error) && (
          <Alert variant="destructive">
            <AlertDescription>{uploadError || error}</AlertDescription>
          </Alert>
        )}

        {files.length > 0 && (
          <div className="space-y-2">
            <p className="text-sm font-medium">Selected files:</p>
            {files.map((file, index) => (
              <div
                key={index}
                className="flex items-center justify-between p-2 bg-muted rounded-md"
              >
                <div className="flex items-center gap-2">
                  <File className="h-4 w-4 text-muted-foreground" />
                  <span className="text-sm">{file.name}</span>
                  <span className="text-xs text-muted-foreground">
                    ({(file.size / 1024 / 1024).toFixed(2)} MB)
                  </span>
                </div>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => removeFile(index)}
                  disabled={isLoading}
                >
                  <X className="h-4 w-4" />
                </Button>
              </div>
            ))}
            
            <Button
              onClick={handleUpload}
              disabled={isLoading || files.length === 0}
              className="w-full"
            >
              {isLoading ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Uploading...
                </>
              ) : (
                <>
                  <Upload className="mr-2 h-4 w-4" />
                  Upload {files.length} file{files.length > 1 ? 's' : ''}
                </>
              )}
            </Button>
          </div>
        )}
      </CardContent>
    </Card>
  );
}