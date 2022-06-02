//import { useState, useEffect, useRef } from 'react';
import { Box, Card } from '@mui/material';
import PropTypes from 'prop-types';

/**
 * props
 * * data - The Document object from the JSON
 */

function JSONPage(props) {


  return (
    <Box sx={{flexGrow: 1, overflowY: "auto"}}>
      <Card variant='outlined' sx={{margin: "4px", height: "inherit"}}>
      {
        props.data !== null ? <pre>{JSON.stringify(props.data, null, 2)}</pre> : <p>No Data</p>
      }
      </Card>
    </Box>
  )
} // JSONPage

JSONPage.propTypes = {
  'data': PropTypes.object.isRequired
}

export default JSONPage