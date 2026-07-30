import { Button, Container, Stack, Typography } from "@mui/material";
import { Link } from "react-router-dom";

export function NotFoundPage() {
  return (
    <Container maxWidth="sm" sx={{ py: 12 }}>
      <Stack spacing={2} alignItems="flex-start">
        <Typography color="primary.main" fontWeight={700}>
          404
        </Typography>
        <Typography variant="h2">That view isn’t available.</Typography>
        <Typography color="text.secondary">
          The foundation is running, but the requested route does not exist.
        </Typography>
        <Button component={Link} to="/" variant="contained">
          Return to platform status
        </Button>
      </Stack>
    </Container>
  );
}
