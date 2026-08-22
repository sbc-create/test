import type { ServerFunctionClient } from 'payload'

import config from '@payload-config'
import { importMap } from './admin/importMap.js'
import { RootLayout, handleServerFunctions } from '@payloadcms/next/layouts'
import React from 'react'

import '@payloadcms/next/css'

type Args = { children: React.ReactNode }

const serverFunction: ServerFunctionClient = async function (args) {
  'use server'
  return handleServerFunctions({ ...args, config, importMap })
}

const Layout = ({ children }: Args) => (
  <RootLayout config={config} importMap={importMap} serverFunction={serverFunction}>
    {children}
  </RootLayout>
)

export default Layout
