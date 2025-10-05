"use client";

import LeafyGreenProvider from '@leafygreen-ui/leafygreen-provider';

export default function LeafyGreenProviderWrapper({ children }) {
  return <LeafyGreenProvider>{children}</LeafyGreenProvider>;
}
