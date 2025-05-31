'use client';

import { useState, useCallback } from 'react';
import { Upload, FileText, AlertCircle, CheckCircle, Link, Database } from 'lucide-react';
import { useDropzone } from 'react-dropzone';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Progress } from '@/components/ui/progress';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';

interface FileInfo {
  file: File;
  status: 'pending' | 'uploading' | 'analyzing' | 'complete' | 'error';
  preview?: {
    rows: number;
    columns: string[];
  };
  relationships?: RelationshipInfo[];
}

interface RelationshipInfo {
  fromTable: string;
  fromColumn: string;
  toTable: string;
  toColumn: string;
  confidence: number;
  type: 'one-to-one' | 'one-to-many' | 'many-to-many';
}

interface ValidationIssue {
  severity: 'error' | 'warning' | 'info';
  message: string;
  suggestion?: string;
}

export function MultiFileUpload() {
  const [files, setFiles] = useState<FileInfo[]>([]);
  const [relationships, setRelationships] = useState<RelationshipInfo[]>([]);
  const [validationIssues, setValidationIssues] = useState<ValidationIssue[]>([]);
  const [isProcessing, setIsProcessing] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);

  const onDrop = useCallback((acceptedFiles: File[]) => {
    const newFiles = acceptedFiles.map(file => ({
      file,
      status: 'pending' as const,
    }));
    setFiles(prev => [...prev, ...newFiles]);
  }, []);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      'text/csv': ['.csv'],
      'application/vnd.ms-excel': ['.xls'],
      'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': ['.xlsx'],
    },
    multiple: true,
  });

  const processFiles = async () => {
    setIsProcessing(true);
    setUploadProgress(0);

    // Simulate file processing
    for (let i = 0; i < files.length; i++) {
      setFiles(prev => prev.map((f, idx) => 
        idx === i ? { ...f, status: 'uploading' } : f
      ));
      
      // Simulate upload progress
      await new Promise(resolve => setTimeout(resolve, 1000));
      setUploadProgress((i + 1) / files.length * 50);

      setFiles(prev => prev.map((f, idx) => 
        idx === i ? { 
          ...f, 
          status: 'analyzing',
          preview: {
            rows: Math.floor(Math.random() * 1000) + 100,
            columns: ['id', 'name', 'email', 'created_at']
          }
        } : f
      ));
    }

    // Simulate relationship detection
    await new Promise(resolve => setTimeout(resolve, 1500));
    setUploadProgress(75);

    // Mock relationships
    setRelationships([
      {
        fromTable: 'customers',
        fromColumn: 'id',
        toTable: 'orders',
        toColumn: 'customer_id',
        confidence: 0.95,
        type: 'one-to-many'
      },
      {
        fromTable: 'products',
        fromColumn: 'id',
        toTable: 'order_items',
        toColumn: 'product_id',
        confidence: 0.90,
        type: 'one-to-many'
      }
    ]);

    // Mock validation
    setValidationIssues([
      {
        severity: 'warning',
        message: 'Found 5 orphaned records in orders.customer_id',
        suggestion: 'These orders reference customers that don\'t exist in the customers table'
      },
      {
        severity: 'info',
        message: 'Detected e-commerce data model',
        suggestion: 'Try queries like "Total revenue by customer" or "Top selling products"'
      }
    ]);

    setUploadProgress(100);
    setFiles(prev => prev.map(f => ({ ...f, status: 'complete' })));
    setIsProcessing(false);
  };

  const getFileIcon = (status: FileInfo['status']) => {
    switch (status) {
      case 'complete':
        return <CheckCircle className="h-4 w-4 text-green-500" />;
      case 'error':
        return <AlertCircle className="h-4 w-4 text-red-500" />;
      default:
        return <FileText className="h-4 w-4 text-gray-500" />;
    }
  };

  return (
    <div className="space-y-6">
      {/* Upload Area */}
      <Card>
        <CardHeader>
          <CardTitle>Upload Your Data Files</CardTitle>
          <CardDescription>
            Upload multiple related files (CSV, Excel) to create a complete data product
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div
            {...getRootProps()}
            className={`
              border-2 border-dashed rounded-lg p-8 text-center cursor-pointer
              transition-colors duration-200 ease-in-out
              ${isDragActive ? 'border-blue-500 bg-blue-50' : 'border-gray-300 hover:border-gray-400'}
            `}
          >
            <input {...getInputProps()} />
            <Upload className="mx-auto h-12 w-12 text-gray-400" />
            <p className="mt-2 text-sm text-gray-600">
              {isDragActive
                ? 'Drop the files here...'
                : 'Drag & drop files here, or click to select'}
            </p>
            <p className="mt-1 text-xs text-gray-500">
              Supports CSV and Excel files
            </p>
          </div>

          {/* File List */}
          {files.length > 0 && (
            <div className="mt-4 space-y-2">
              {files.map((fileInfo, index) => (
                <div
                  key={index}
                  className="flex items-center justify-between p-2 bg-gray-50 rounded"
                >
                  <div className="flex items-center space-x-2">
                    {getFileIcon(fileInfo.status)}
                    <span className="text-sm">{fileInfo.file.name}</span>
                    {fileInfo.preview && (
                      <Badge variant="secondary" className="text-xs">
                        {fileInfo.preview.rows} rows
                      </Badge>
                    )}
                  </div>
                  <Badge
                    variant={fileInfo.status === 'complete' ? 'default' : 'secondary'}
                  >
                    {fileInfo.status}
                  </Badge>
                </div>
              ))}
            </div>
          )}

          {/* Process Button */}
          {files.length > 0 && !isProcessing && files.every(f => f.status === 'pending') && (
            <Button onClick={processFiles} className="w-full mt-4">
              Process Files and Detect Relationships
            </Button>
          )}

          {/* Progress */}
          {isProcessing && (
            <div className="mt-4">
              <Progress value={uploadProgress} className="h-2" />
              <p className="text-sm text-gray-600 mt-2 text-center">
                Processing files... {uploadProgress}%
              </p>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Results */}
      {relationships.length > 0 && (
        <Tabs defaultValue="relationships" className="w-full">
          <TabsList className="grid w-full grid-cols-3">
            <TabsTrigger value="relationships">Relationships</TabsTrigger>
            <TabsTrigger value="validation">Validation</TabsTrigger>
            <TabsTrigger value="suggestions">Query Suggestions</TabsTrigger>
          </TabsList>

          <TabsContent value="relationships">
            <Card>
              <CardHeader>
                <CardTitle>Detected Relationships</CardTitle>
                <CardDescription>
                  We found these connections between your tables
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div className="space-y-3">
                  {relationships.map((rel, index) => (
                    <div
                      key={index}
                      className="flex items-center justify-between p-3 border rounded-lg"
                    >
                      <div className="flex items-center space-x-3">
                        <Database className="h-4 w-4 text-gray-500" />
                        <span className="font-mono text-sm">
                          {rel.fromTable}.{rel.fromColumn}
                        </span>
                        <Link className="h-4 w-4 text-blue-500" />
                        <span className="font-mono text-sm">
                          {rel.toTable}.{rel.toColumn}
                        </span>
                      </div>
                      <div className="flex items-center space-x-2">
                        <Badge variant="outline">{rel.type}</Badge>
                        <Badge
                          variant={rel.confidence > 0.8 ? 'default' : 'secondary'}
                        >
                          {Math.round(rel.confidence * 100)}% confident
                        </Badge>
                      </div>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          </TabsContent>

          <TabsContent value="validation">
            <Card>
              <CardHeader>
                <CardTitle>Data Validation</CardTitle>
                <CardDescription>
                  Issues found while analyzing your data
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div className="space-y-3">
                  {validationIssues.map((issue, index) => (
                    <Alert
                      key={index}
                      variant={issue.severity === 'error' ? 'destructive' : 'default'}
                    >
                      <AlertCircle className="h-4 w-4" />
                      <AlertDescription>
                        <div className="font-medium">{issue.message}</div>
                        {issue.suggestion && (
                          <div className="text-sm mt-1 opacity-90">
                            {issue.suggestion}
                          </div>
                        )}
                      </AlertDescription>
                    </Alert>
                  ))}
                </div>
              </CardContent>
            </Card>
          </TabsContent>

          <TabsContent value="suggestions">
            <Card>
              <CardHeader>
                <CardTitle>Suggested Queries</CardTitle>
                <CardDescription>
                  Based on your data model, try these queries
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div className="space-y-2">
                  <Button variant="outline" className="w-full justify-start">
                    Show total revenue by customer
                  </Button>
                  <Button variant="outline" className="w-full justify-start">
                    Find top 10 best-selling products
                  </Button>
                  <Button variant="outline" className="w-full justify-start">
                    Calculate average order value by month
                  </Button>
                  <Button variant="outline" className="w-full justify-start">
                    Show customer purchase frequency
                  </Button>
                </div>
              </CardContent>
            </Card>
          </TabsContent>
        </Tabs>
      )}
    </div>
  );
}