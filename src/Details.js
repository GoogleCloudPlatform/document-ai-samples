/*
# Copyright 2022, Google, Inc.
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
*/
import { useState } from 'react';
import { Box, Typography, TableContainer, TableHead, TableRow, TableCell, TableBody, Table, Paper, Card, CardContent, Stack, IconButton } from '@mui/material';
import EntityInfoDialog from './EntityInfoDialog';
import InfoIcon from '@mui/icons-material/Info';
import PropTypes from 'prop-types';
import NoData from './NoData';

/**
 * props
 * * data - The JSON object
 * @param {*} props 
 * @returns 
 */
function Details(props) {
  const [open, setOpen] = useState(false)
  const [entity, setEntity] = useState(null)
  if (props.data === null) {
    return <NoData />
  }
  const doc = props.data;
  return (
    <Box sx={{ overflowY: "auto" }}>
      <Paper sx={{ margin: "4px" }}>
        <Stack direction="column" spacing={1}>
          <Card variant="outlined">
            <CardContent>
              <Typography variant="h6">Details</Typography>
              <Typography variant="body1" component="ul">
                <li>Uri: {doc.uri ? doc.uri : "<none>"}</li>
                <li>MimeType: {doc.mimeType}</li>
                <li>Page Count: {doc.pages.length}</li>
                <li>Human review status: {props.data.humanReviewStatus?props.data.humanReviewStatus.state:"undefined"}</li>
              </Typography>
            </CardContent>
          </Card>
          <Card variant="outlined">
            <CardContent>
              <Typography variant="h6">Pages</Typography>
              <TableContainer>
                <Table size="smalll">
                  <TableHead>
                    <TableRow>
                      <TableCell>Page Number</TableCell>
                      <TableCell>Width</TableCell>
                      <TableCell >Height</TableCell>
                      <TableCell>Units</TableCell>
                      <TableCell>Languages</TableCell>
                      <TableCell>Blocks</TableCell>
                      <TableCell>Paragraphs</TableCell>
                      <TableCell>Lines</TableCell>
                      <TableCell>Tokens</TableCell>
                      <TableCell>Tables</TableCell>
                      <TableCell>Form Fields</TableCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {doc.pages.map((page) => (
                      <TableRow key={page.pageNumber}>
                        <TableCell>
                          {page.pageNumber}
                        </TableCell>
                        <TableCell>{page.dimension?page.dimension.width:"undefined"}</TableCell>
                        <TableCell>{page.dimension?page.dimension.height:"undefined"}</TableCell>
                        <TableCell>{page.dimension?page.dimension.unit:"undefined"}</TableCell>
                        <TableCell>{page.detectedLanguages?page.detectedLanguages.map((detectedLanguage) => (`${detectedLanguage.languageCode} `)):"undefined"}</TableCell>
                        <TableCell>{page.blocks?page.blocks.length:"undefined"}</TableCell>
                        <TableCell>{page.paragraphs?page.paragraphs.length:"undefined"}</TableCell>
                        <TableCell>{page.lines?page.lines.length:"undefined"}</TableCell>
                        <TableCell>{page.tokens?page.tokens.length:"undefined"}</TableCell>
                        <TableCell>{page.tables?page.tables.length:"undefined"}</TableCell>
                        <TableCell>{page.formFields?page.formFields.length:"undefined"}</TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </TableContainer>
            </CardContent>
          </Card>
          {
            //
            // ENTITIES
            //
          }
          <Card variant="outlined">
            <CardContent>
              <Typography variant="h6">Entities</Typography>
              <TableContainer>
                <Table size="smalll">
                  <TableHead>
                    <TableRow>
                      <TableCell>ID</TableCell>
                      <TableCell>Type</TableCell>
                      <TableCell>Confidence</TableCell>
                      <TableCell>Text</TableCell>
                      <TableCell>Normalized</TableCell>
                      <TableCell>Properties</TableCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {doc.entities.map((entity) => (
                      <TableRow key={entity.id}>
                        <TableCell>
                          <IconButton color="primary" size="small" onClick={() => { setOpen(true); setEntity(entity) }}>
                            <InfoIcon />
                          </IconButton>
                          {entity.id}
                        </TableCell>
                        <TableCell>{entity.type}</TableCell>
                        <TableCell>{entity.confidence}</TableCell>
                        <TableCell>{entity.mentionText}</TableCell>
                        <TableCell>{entity.normalizedValue ? entity.normalizedValue.text : ""}</TableCell>
                        <TableCell>{entity.properties ? entity.properties.length : 0}</TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </TableContainer>
            </CardContent>
          </Card>
        </Stack>
      </Paper>
      <EntityInfoDialog open={open} entity={entity} close={() => { setOpen(false) }} />
    </Box >
  )
} // Details

Details.propTypes = {
  'data': PropTypes.object.isRequired
}

export default Details