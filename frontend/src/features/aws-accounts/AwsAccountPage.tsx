import {
  CloudQueueRounded,
  Inventory2Rounded,
  RefreshRounded,
  SecurityRounded,
} from "@mui/icons-material";
import {
  Alert,
  Box,
  Button,
  Card,
  CardContent,
  Chip,
  CircularProgress,
  Container,
  FormControl,
  Grid,
  InputLabel,
  MenuItem,
  Select,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Typography,
} from "@mui/material";
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { logout } from "../identity/api";
import { clearSession } from "../identity/session";
import { ConnectionOnboarding } from "./ConnectionOnboarding";
import { getAwsIdentity, getEc2Inventory } from "./api";

const regions = ["us-east-1", "us-west-2", "eu-west-1", "ap-south-1"];

export function AwsAccountPage() {
  const [region, setRegion] = useState("us-east-1");
  const navigate = useNavigate();
  const identity = useQuery({
    queryKey: ["aws-identity", region],
    queryFn: ({ signal }) => getAwsIdentity(region, signal),
  });
  const inventory = useQuery({
    queryKey: ["ec2-inventory", region],
    queryFn: ({ signal }) => getEc2Inventory(region, signal),
  });
  const error = identity.error ?? inventory.error;

  async function signOut() {
    try {
      await logout();
    } finally {
      clearSession();
      void navigate("/login", { replace: true });
    }
  }

  return (
    <Box component="main" className="app-shell">
      <Container maxWidth="lg" sx={{ py: { xs: 4, md: 7 } }}>
        <Stack spacing={4}>
          <Stack
            direction={{ xs: "column", sm: "row" }}
            justifyContent="space-between"
            gap={2}
          >
            <Box>
              <Typography
                color="primary.main"
                fontWeight={700}
                letterSpacing=".08em"
              >
                AWS ACCOUNT
              </Typography>
              <Typography variant="h2" mt={1}>
                Account visibility
              </Typography>
              <Typography color="text.secondary" mt={1}>
                Read-only identity and EC2 inventory from the configured AWS
                role.
              </Typography>
            </Box>
            <Stack direction="row" spacing={1} alignItems="center">
              <FormControl size="small" sx={{ minWidth: 145 }}>
                <InputLabel id="region-label">Region</InputLabel>
                <Select
                  labelId="region-label"
                  value={region}
                  label="Region"
                  onChange={(event) => setRegion(event.target.value)}
                >
                  {regions.map((item) => (
                    <MenuItem key={item} value={item}>
                      {item}
                    </MenuItem>
                  ))}
                </Select>
              </FormControl>
              <Button component={Link} to="/" variant="outlined">
                Platform
              </Button>
              <Button
                color="inherit"
                onClick={() => {
                  void signOut();
                }}
              >
                Sign out
              </Button>
            </Stack>
          </Stack>

          {error && (
            <Alert severity="error" role="alert">
              {error.message}
            </Alert>
          )}

          <Grid container spacing={2}>
            <Grid size={{ xs: 12, md: 7 }}>
              <Card sx={{ height: "100%" }}>
                <CardContent sx={{ p: 3 }}>
                  <Stack spacing={2}>
                    <Stack direction="row" spacing={1.5} alignItems="center">
                      <SecurityRounded color="primary" />
                      <Typography variant="h6">Verified identity</Typography>
                    </Stack>
                    {identity.isLoading ? (
                      <CircularProgress size={26} />
                    ) : (
                      identity.data && (
                        <Stack spacing={1.25}>
                          <Typography color="text.secondary">
                            Account ID
                          </Typography>
                          <Typography variant="h5" fontFamily="monospace">
                            {identity.data.account_id}
                          </Typography>
                          <Typography color="text.secondary">
                            Principal
                          </Typography>
                          <Typography sx={{ overflowWrap: "anywhere" }}>
                            {identity.data.principal_arn}
                          </Typography>
                          <Stack direction="row" spacing={1}>
                            <Chip
                              label={identity.data.authentication_type}
                              color="success"
                              size="small"
                            />
                            <Chip
                              label={identity.data.region}
                              variant="outlined"
                              size="small"
                            />
                          </Stack>
                        </Stack>
                      )
                    )}
                  </Stack>
                </CardContent>
              </Card>
            </Grid>
            <Grid size={{ xs: 12, md: 5 }}>
              <Card sx={{ height: "100%" }}>
                <CardContent sx={{ p: 3 }}>
                  <Stack spacing={2}>
                    <Stack direction="row" spacing={1.5} alignItems="center">
                      <Inventory2Rounded color="primary" />
                      <Typography variant="h6">EC2 inventory</Typography>
                    </Stack>
                    {inventory.isLoading ? (
                      <CircularProgress size={26} />
                    ) : (
                      inventory.data && (
                        <>
                          <Typography variant="h2">
                            {inventory.data.resource_count}
                          </Typography>
                          <Typography color="text.secondary">
                            instances in {inventory.data.region}
                          </Typography>
                        </>
                      )
                    )}
                    <Button
                      variant="outlined"
                      startIcon={<RefreshRounded />}
                      onClick={() => {
                        void identity.refetch();
                        void inventory.refetch();
                      }}
                      disabled={identity.isFetching || inventory.isFetching}
                    >
                      Refresh inventory
                    </Button>
                  </Stack>
                </CardContent>
              </Card>
            </Grid>
          </Grid>

          <Card>
            <CardContent sx={{ p: 0 }}>
              <Stack
                direction="row"
                spacing={1.5}
                alignItems="center"
                sx={{ p: 3, pb: 2 }}
              >
                <CloudQueueRounded color="primary" />
                <Typography variant="h6">EC2 resources</Typography>
              </Stack>
              <TableContainer>
                <Table>
                  <TableHead>
                    <TableRow>
                      <TableCell>Name</TableCell>
                      <TableCell>Instance type</TableCell>
                      <TableCell>State</TableCell>
                      <TableCell>Availability zone</TableCell>
                      <TableCell>Public IP</TableCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {inventory.data?.resources.map((resource) => (
                      <TableRow key={resource.resource_id}>
                        <TableCell>
                          {resource.name || "Unnamed instance"}
                        </TableCell>
                        <TableCell>{resource.instance_type}</TableCell>
                        <TableCell>
                          <Chip
                            label={resource.state}
                            size="small"
                            color={
                              resource.state === "running"
                                ? "success"
                                : "default"
                            }
                          />
                        </TableCell>
                        <TableCell>{resource.availability_zone}</TableCell>
                        <TableCell>{resource.public_ip ?? "—"}</TableCell>
                      </TableRow>
                    ))}
                    {inventory.data?.resources.length === 0 && (
                      <TableRow>
                        <TableCell colSpan={5}>
                          <Typography color="text.secondary" sx={{ p: 2 }}>
                            No EC2 instances found in this region.
                          </Typography>
                        </TableCell>
                      </TableRow>
                    )}
                  </TableBody>
                </Table>
              </TableContainer>
            </CardContent>
          </Card>
          <ConnectionOnboarding region={region} />
        </Stack>
      </Container>
    </Box>
  );
}
