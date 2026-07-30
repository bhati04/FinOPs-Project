import {
  Alert,
  Button,
  Card,
  CardContent,
  Chip,
  Grid,
  Stack,
  TextField,
  Typography,
} from "@mui/material";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { createConnection, listConnections, verifyConnection } from "./api";

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
  const error = create.error ?? verify.error ?? connections.error;

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
              </Stack>
            </Stack>
          </CardContent>
        </Card>
      ))}
    </Stack>
  );
}
