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
import { AppBar, Input, Toolbar, Box as Card, Button, Typography, Tab, Tabs, Divider, IconButton } from '@mui/material';
import Details from './Details';
import JSONPage from './JSONPage';
import DocAIView from './DocAIView';
import AboutDialog from './About';
import HelpIcon from '@mui/icons-material/Help';
//import PropTypes from 'prop-types';

/**
 * props:
 * - None
 * @param {*} props 
 * @returns 
 */
function DocAITopLevel(props) {
  const [tabValue, setTabValue] = useState(0);
  const [data, setData] = useState(null);
  const [aboutOpen, setAboutOpen] = useState(false);

  function tabChange(event, newValue) {
    setTabValue(newValue);
  };

  function loadJson(event) {
    //debugger;
    if (event.target.files.length === 0) {
      setData(null);
      return;
    }

    // Create a file reader to read the file from the local file system.  Read the file as a binary string.
    // We have registered an onload() call back to be called when the file has been loaded.
    const fileReader = new FileReader();
    fileReader.onload = () => {
      //console.dir()
      try {
        const newData = JSON.parse(fileReader.result);
        if (newData.hasOwnProperty("document")) {
          setData(newData.document);
        } else {
          setData(newData);
        }        
      }
      catch (e) {
        console.log(`ERROR: ${e}`)
        setData(null);
      }
    }
    fileReader.readAsBinaryString(event.target.files[0]); // When the file has been read, the onload() will be invoked.
  }
  return (
    <Card sx={{ height: "100%", display: "flex", flexDirection: "column" }}>
      <AppBar position="static">
        <Toolbar>
          <Typography variant="h6" style={{ flexGrow: 1 }}>
            Document AI Dev
          </Typography>
          <label htmlFor="contained-button-file">
            <Input
              style={{ display: "none" }}
              accept=".json"
              id="contained-button-file"
              multiple type="file"
              onChange={loadJson} />
            <Button color="inherit" component="span">
              Load JSON
            </Button>
          </label>
          <IconButton color="inherit" onClick={() => setAboutOpen(true)}>
            <HelpIcon />
          </IconButton>
        </Toolbar>
      </AppBar>
      <Tabs value={tabValue} onChange={tabChange}>
        <Tab label="Document" />
        <Tab label="JSON" />
        <Tab label="Details" />
      </Tabs>
      <Divider />
      <Card variant='outlined' sx={{ flexGrow: 1, flexShrink: 1, overflow: "hidden", display: "flex", flexDirection: "column" }}>
        {
          tabValue === 0 && <DocAIView data={data} />
        }
        {
          tabValue === 1 &&
          <JSONPage data={data} />
        }
        {
          tabValue === 2 &&
          <Details data={data} />
        }
      </Card>
      <AboutDialog open={aboutOpen} close={() => setAboutOpen(false)}/>
    </Card>

  )
} // DocAITopLevel


DocAITopLevel.propTypes = {
}

export default DocAITopLevel