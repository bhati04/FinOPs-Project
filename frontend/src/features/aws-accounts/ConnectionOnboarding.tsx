import {
  Alert,
  Button,
  Card,
  CardContent,
  Chip,
  Grid,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  TextField,
  Typography,
} from "@mui/material";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import {
  createConnection,
  listConnections,
  listInventoryScans,
  listPersistedResources,
  startInventoryScan,
  verifyConnection,
} from "./api";

export function ConnectionOnboarding({ region }: { region: string }) {
  const [alias, setAlias] = useState("");
  const [accountId, setAccountId] = useState("");
  const [roleArn, setRoleArn] = useState("");
  const [externalId, setExternalId] = useState<string>();
  const queryClient = useQueryClient();
  const connections = useQuery({
    queryKey: ["aws-connections"],
    queryFn: ({ signal }) => listConnections(signal),
  });
  const scans = useQuery({
    queryKey: ["inventory-scans"],
    queryFn: ({ signal }) => listInventoryScans(signal),
    refetchInterval: (query) =>
      query.state.data?.some(
        (scan) => scan.status === "queued" || scan.status === "running",
      )
        ? 3000
        : false,
  });
  const persistedResources = useQuery({
    queryKey: ["persisted-resources", region],
    queryFn: ({ signal }) => listPersistedResources(region, signal),
    refetchInterval: 5000,
  });
  const create = useMutation({
    mutationFn: createConnection,
    onSuccess: async (connection) => {
      setExternalId(connection.external_id ?? undefined);
      await queryClient.invalidateQueries({ queryKey: ["aws-connections"] });
    },
  });
  const verify = useMutation({
    mutationFn: (id: string) => verifyConnection(id, region),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["aws-connections"] });
    },
  });
  const startScan = useMutation({
    mutationFn: (id: string) => startInventoryScan(id, region),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["inventory-scans"] });
    },
  });
  const error =
    create.error ??
    verify.error ??
    startScan.error ??
    connections.error ??
    scans.error ??
    persistedResources.error;

  const scanByConnection = new Map<
    string,
    NonNullable<typeof scans.data>[number]
  >();
  for (const scan of scans.data ?? []) {
    if (!scanByConnection.has(scan.connection_id)) {
      scanByConnection.set(scan.connection_id, scan);
    }
  }

  return (
    <Stack spacing={2}>
      <Typography variant="h5">Customer AWS connections</Typography>
      <Typography color="text.secondary">
        Connect a customer-managed read-only role using a unique External ID.
      </Typography>
      {error && <Alert severity="error">{error.message}</Alert>}
      {externalId && (
        <Alert severity="info">
          External ID: <strong>{externalId}</strong>. Add this value to the role
          trust policy before verification. It is shown only when the draft is
          created.
        </Alert>
      )}
      <Card>
        <CardContent>
          <Grid container spacing={2}>
            <Grid size={{ xs: 12, md: 3 }}>
              <TextField
                fullWidth
                label="Account alias"
                value={alias}
                onChange={(event) => setAlias(event.target.value)}
              />
            </Grid>
            <Grid size={{ xs: 12, md: 3 }}>
              <TextField
                fullWidth
                label="12-digit account ID"
                value={accountId}
                onChange={(event) => setAccountId(event.target.value)}
              />
            </Grid>
            <Grid size={{ xs: 12, md: 4 }}>
              <TextField
                fullWidth
                label="Read-only role ARN"
                value={roleArn}
                onChange={(event) => setRoleArn(event.target.value)}
              />
            </Grid>
            <Grid size={{ xs: 12, md: 2 }}>
              <Button
                fullWidth
                variant="contained"
                sx={{ height: "56px" }}
                disabled={
                  !alias ||
                  !/^\d{12}$/.test(accountId) ||
                  !roleArn ||
                  create.isPending
                }
                onClick={() =>
                  create.mutate({
                    alias,
                    expected_account_id: accountId,
                    role_arn: roleArn,
                  })
                }
              >
                Create draft
              </Button>
            </Grid>
          </Grid>
        </CardContent>
      </Card>
      {connections.data?.map((connection) => (
        <Card key={connection.id}>
          <CardContent>
            <Stack
              direction={{ xs: "column", md: "row" }}
              justifyContent="space-between"
              gap={2}
            >
              <Stack>
                <Typography fontWeight={700}>{connection.alias}</Typography>
                <Typography color="text.secondary">
                  {connection.expected_account_id}
                </Typography>
                <Typography variant="body2" sx={{ overflowWrap: "anywhere" }}>
                  {connection.role_arn}
                </Typography>
              </Stack>
              <Stack direction="row" spacing={1} alignItems="center">
                <Chip
                  label={connection.status}
                  color={
                    connection.status === "verified"
                      ? "success"
                      : connection.status === "failed"
                        ? "error"
                        : "warning"
                  }
                />
                {connection.status !== "verified" && (
                  <Button
                    variant="outlined"
                    disabled={verify.isPending}
                    onClick={() => verify.mutate(connection.id)}
                  >
                    Verify role
                  </Button>
                )}
                {connection.status === "verified" && (
                  <Button
                    variant="contained"
                    disabled={
                      startScan.isPending ||
                      ["queued", "running"].includes(
                        scanByConnection.get(connection.id)?.status ?? "",
                      )
                    }
                    onClick={() => startScan.mutate(connection.id)}
                  >
                    {["queued", "running"].includes(
                      scanByConnection.get(connection.id)?.status ?? "",
                    )
                      ? "Scan running"
                      : "Scan EC2"}
                  </Button>
                )}
              </Stack>
            </Stack>
          </CardContent>
        </Card>
      ))}
      <Card>
        <CardContent>
          <Typography variant="h6" mb={2}>
            Inventory scan history
          </Typography>
          <TableContainer>
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell>Connection</TableCell>
                  <TableCell>Region</TableCell>
                  <TableCell>Status</TableCell>
                  <TableCell>Resources</TableCell>
                  <TableCell>Started</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {scans.data?.map((scan) => (
                  <TableRow key={scan.id}>
                    <TableCell>
                      {connections.data?.find(
                        (connection) => connection.id === scan.connection_id,
                      )?.alias ?? "Connection"}
                    </TableCell>
                    <TableCell>{scan.region}</TableCell>
                    <TableCell>
                      <Chip
                        size="small"
                        label={scan.status}
                        color={
                          scan.status === "completed"
                            ? "success"
                            : scan.status === "failed"
                              ? "error"
                              : "warning"
                        }
                      />
                    </TableCell>
                    <TableCell>{scan.resource_count}</TableCell>
                    <TableCell>
                      {new Date(scan.created_at).toLocaleString()}
                    </TableCell>
                  </TableRow>
                ))}
                {scans.data?.length === 0 && (
                  <TableRow>
                    <TableCell colSpan={5}>
                      No persisted scans yet. Start one from a verified
                      connection.
                    </TableCell>
                  </TableRow>
                )}
              </TableBody>
            </Table>
          </TableContainer>
        </CardContent>
      </Card>
      <Card>
        <CardContent>
          <Typography variant="h6" mb={2}>
            Persisted EC2 inventory
          </Typography>
          <Typography color="text.secondary" mb={2}>
            {persistedResources.data?.length ?? 0} resources stored for {region}
          </Typography>
          <TableContainer>
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell>Name</TableCell>
                  <TableCell>Resource ID</TableCell>
                  <TableCell>Type</TableCell>
                  <TableCell>State</TableCell>
                  <TableCell>Discovered</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {persistedResources.data?.map((resource) => (
                  <TableRow key={resource.id}>
                    <TableCell>{resource.name || "Unnamed"}</TableCell>
                    <TableCell sx={{ fontFamily: "monospace" }}>
                      {resource.resource_id}
                    </TableCell>
                    <TableCell>{resource.resource_type}</TableCell>
                    <TableCell>{resource.state}</TableCell>
                    <TableCell>
                      {new Date(resource.discovered_at).toLocaleString()}
                    </TableCell>
                  </TableRow>
                ))}
                {persistedResources.data?.length === 0 && (
                  <TableRow>
                    <TableCell colSpan={5}>
                      No persisted EC2 resources in this region.
                    </TableCell>
                  </TableRow>
                )}
              </TableBody>
            </Table>
          </TableContainer>
        </CardContent>
      </Card>
    </Stack>
  );
}
